// Bot de WhatsApp do IA Shopee (separado de qualquer outro projeto).
// Várias "sessões" (um número de WhatsApp por robô). API só local: http://127.0.0.1:3101
//   GET  /status?sessao=dono      GET /qr?sessao=dono (página com o QR Code para escanear)
//   POST /texto {sessao, para, texto}     POST /video {sessao, para, arquivo, legenda}     POST /sair {sessao}
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import makeWASocket, { Browsers, DisconnectReason, fetchLatestBaileysVersion, useMultiFileAuthState, downloadMediaMessage } from '@whiskeysockets/baileys'
import pino from 'pino'
import QRCode from 'qrcode'

const DIR = path.dirname(fileURLToPath(import.meta.url))
const PORT = Number(process.env.IA_WA_PORT || 3101)
const ROBOS = JSON.parse(fs.readFileSync(path.join(DIR, '..', 'config', 'robos.json'), 'utf8'))
const sessoes = {}  // nome -> {sock, status, qr}
// Só o dono pode mandar gravações para o robô guardar (número e endereço interno do WhatsApp)
const DONO = (process.env.IA_WA_DONO || '553173410138,29205794390184').split(',')
const GRAV = path.join(DIR, '..', 'gravacoes')
const espera = ms => new Promise(r => setTimeout(r, ms))

async function iniciar(nome) {
  const s = sessoes[nome] ||= { status: 'iniciando', qr: null, sock: null }
  const AUTH = path.join(DIR, 'auth', nome)
  const { state, saveCreds } = await useMultiFileAuthState(AUTH)
  let version
  try { ({ version } = await fetchLatestBaileysVersion()) } catch { }
  const sock = makeWASocket({ auth: state, version, logger: pino({ level: 'silent' }), browser: Browsers.ubuntu('Chrome'), markOnlineOnConnect: false, syncFullHistory: false })
  s.sock = sock
  sock.ev.on('creds.update', saveCreds)
  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify') return
    for (const m of messages) {
      try {
        const de = (m.key.remoteJid || '').split('@')[0].split(':')[0]
        if (m.key.fromMe || !DONO.includes(de)) continue
        const msg = m.message || {}
        const tipo = msg.audioMessage ? 'audio' : msg.videoMessage ? 'video' : msg.imageMessage ? 'foto' : null
        if (!tipo) continue
        const ext = { audio: msg.audioMessage?.mimetype?.includes('ogg') ? 'ogg' : 'm4a', video: 'mp4', foto: 'jpg' }[tipo]
        const buf = await downloadMediaMessage(m, 'buffer', {}, { reuploadRequest: sock.updateMediaMessage })
        fs.mkdirSync(path.join(GRAV, tipo), { recursive: true })
        const arq = path.join(GRAV, tipo, `${new Date().toISOString().replace(/[:.]/g, '-')}.${ext}`)
        fs.writeFileSync(arq, buf)
        console.log(`[${nome}] gravação salva: ${arq}`)
        await sock.sendMessage(m.key.remoteJid, { text: `✅ ${tipo} guardado (${Math.round(buf.length / 1024)} KB)` }, { quoted: m })
      } catch (e) { console.error('erro ao guardar gravação', e) }
    }
  })
  sock.ev.on('messages.update', ups => { for (const u of ups) if (u.update?.status !== undefined) console.log(`[${nome}] recibo ${u.key.remoteJid} ${u.key.id} status=${u.update.status}`) })
  sock.ev.on('message-receipt.update', ups => { for (const u of ups) console.log(`[${nome}] receipt ${u.key.remoteJid} ${u.key.id}`, JSON.stringify(u.receipt)) })
  sock.ev.on('connection.update', async ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      s.status = 'aguardando_qr'; s.qr = qr
      console.log(`[${nome}] escaneie o QR em http://127.0.0.1:${PORT}/qr?sessao=${nome}`)
    }
    if (connection === 'open') { s.status = 'conectado'; s.qr = null; console.log(`[${nome}] conectado`) }
    if (connection === 'close') {
      const code = lastDisconnect?.error?.output?.statusCode
      if (code === DisconnectReason.loggedOut) {
        s.status = 'desconectado'; fs.rmSync(AUTH, { recursive: true, force: true })
        console.log(`[${nome}] saiu da conta; gerando novo QR`)
      } else s.status = 'reconectando'
      await espera(3000); iniciar(nome)
    }
  })
}

async function jid(s, numero) {
  const n = String(numero).replace(/\D/g, '')
  const [r] = await s.sock.onWhatsApp(n)  // corrige o 9º dígito automaticamente
  if (!r?.exists) throw new Error(`número ${n} não tem WhatsApp`)
  if (process.env.IA_WA_LID !== '0') {
    const lid = await s.sock.signalRepository?.lidMapping?.getLIDForPN?.(r.jid)
    console.log('[jid]', r.jid, '-> lid', lid)
    if (lid) return lid
  }
  return r.jid
}

function corpo(req) {
  return new Promise((ok, erro) => { let b = ''; req.on('data', c => b += c); req.on('end', () => { try { ok(JSON.parse(b || '{}')) } catch (e) { erro(e) } }) })
}
function json(res, cod, obj) { res.writeHead(cod, { 'Content-Type': 'application/json; charset=utf-8' }); res.end(JSON.stringify(obj)) }

const fila = {}  // envia uma mensagem por vez por sessão, com pausa natural
function enfileirar(nome, fn, pausa = 4000) {
  const ant = fila[nome] || Promise.resolve()
  const p = ant.catch(() => { }).then(async () => { const r = await fn(); await espera(pausa + Math.random() * pausa * .5); return r })
  fila[nome] = p
  return p
}

http.createServer(async (req, res) => {
  try {
    const u = new URL(req.url, 'http://x')
    const nome = u.searchParams.get('sessao') || 'dono'
    if (req.method === 'GET' && u.pathname === '/status') {
      const s = sessoes[nome]; return json(res, 200, { sessao: nome, status: s?.status || 'inexistente', temQR: !!s?.qr })
    }
    if (req.method === 'GET' && u.pathname === '/qr.png') {
      const s = sessoes[nome]
      if (!s?.qr) { res.writeHead(404); return res.end() }
      res.writeHead(200, { 'Content-Type': 'image/png', 'Cache-Control': 'no-store' })
      return res.end(await QRCode.toBuffer(s.qr, { width: 420, margin: 2 }))
    }
    if (req.method === 'GET' && u.pathname === '/sessoes') {
      return json(res, 200, Object.fromEntries(Object.entries(sessoes).map(([k, v]) => [k, v.status])))
    }
    if (req.method === 'GET' && u.pathname === '/qr') {
      const s = sessoes[nome]
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
      if (s?.status === 'conectado') return res.end(`<h1 style="font-family:sans-serif">✅ ${nome}: WhatsApp conectado</h1>`)
      if (!s?.qr) return res.end(`<meta http-equiv="refresh" content="3"><p style="font-family:sans-serif">Gerando QR... (${s?.status})</p>`)
      const img = await QRCode.toDataURL(s.qr, { width: 420 })
      return res.end(`<meta http-equiv="refresh" content="20"><div style="font-family:sans-serif;text-align:center"><h2>IA Shopee – conectar WhatsApp (${nome})</h2>
        <p>No celular: WhatsApp → Aparelhos conectados → Conectar aparelho</p><img src="${img}"></div>`)
    }
    if (req.method === 'GET' && u.pathname === '/verificar') {
      const s = sessoes[nome]; const n = (u.searchParams.get('numero') || '').replace(/\D/g, '')
      return json(res, 200, { consulta: n, resposta: await s.sock.onWhatsApp(n), sem9: n.length === 13 ? await s.sock.onWhatsApp(n.slice(0, 4) + n.slice(5)) : null })
    }
    if (req.method === 'POST') {
      const b = await corpo(req)
      const s = sessoes[b.sessao || nome]
      if (u.pathname === '/iniciar') {
        const n = String(b.sessao || '').replace(/[^a-z0-9_-]/gi, '')
        if (!n) return json(res, 400, { erro: 'nome inválido' })
        if (!sessoes[n]) iniciar(n)
        return json(res, 200, { ok: true })
      }
      if (u.pathname === '/sair') { try { await s?.sock?.logout() } catch { } return json(res, 200, { ok: true }) }
      if (!s || s.status !== 'conectado') return json(res, 409, { erro: 'sessão não conectada' })
      if (u.pathname === '/texto') {
        const r = await enfileirar(b.sessao, async () => s.sock.sendMessage(await jid(s, b.para), { text: b.texto }))
        return json(res, 200, { ok: true, id: r?.key?.id })
      }
      if (u.pathname === '/video') {
        if (!fs.existsSync(b.arquivo)) return json(res, 400, { erro: 'arquivo não existe' })
        const r = await enfileirar(b.sessao, async () => s.sock.sendMessage(await jid(s, b.para),
          { video: fs.readFileSync(b.arquivo), caption: b.legenda || '', mimetype: 'video/mp4', fileName: path.basename(b.arquivo) }), 15000)
        return json(res, 200, { ok: true, id: r?.key?.id })
      }
    }
    json(res, 404, { erro: 'rota não existe' })
  } catch (e) { console.error(e); json(res, 500, { erro: String(e.message || e) }) }
}).listen(PORT, '127.0.0.1', () => console.log(`[ia-shopee-wa] API local em http://127.0.0.1:${PORT}`))

// inicia o robô principal + todo agente que já tenha login salvo (pasta auth/<nome>)
const iniciais = new Set(Object.values(ROBOS).map(r => r.whatsapp_sessao))
try { for (const d of fs.readdirSync(path.join(DIR, 'auth'))) iniciais.add(d) } catch { }
for (const n of iniciais) iniciar(n)
