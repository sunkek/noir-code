import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import { type Dict, type Lang, I18N, loadLang, saveLang } from './i18n'

const API = import.meta.env.VITE_API_BASE ?? '/api/v1'
const MAX_BYTES = 173
const byteLen = (s: string) => new TextEncoder().encode(s).length

type DecodeResult = {
  ok: boolean
  text: string | null
  confidence: number
  rotation: number | null
  grid_erasures: number
  motif_erasures: number
  cross_check: boolean | null
  failed_stage: string | null
}

async function errorDetail(res: Response): Promise<string> {
  try {
    const j = await res.json()
    return j.error ?? j.detail ?? `HTTP ${res.status}`
  } catch {
    return `HTTP ${res.status}`
  }
}

function Encoder({ t }: { t: Dict }) {
  const [text, setText] = useState('https://noir.example')
  const [style, setStyle] = useState(true)
  const [hatch, setHatch] = useState(true)
  const [adaptive, setAdaptive] = useState(true)
  const [png, setPng] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const bytes = byteLen(text)
  const over = bytes > MAX_BYTES

  async function encode() {
    setErr(null)
    setBusy(true)
    try {
      const res = await fetch(`${API}/encode`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ text, style, hatch_data: hatch, adaptive }),
      })
      if (!res.ok) throw new Error(await errorDetail(res))
      const blob = await res.blob()
      setPng((prev) => {
        if (prev) URL.revokeObjectURL(prev)
        return URL.createObjectURL(blob)
      })
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
      setPng(null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel">
      <h2>{t.encode}</h2>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={4}
        placeholder={t.textPlaceholder}
      />
      <div className={`counter ${over ? 'over' : ''}`}>{t.bytes(bytes, MAX_BYTES)}</div>
      <div className="opts">
        <label><input type="checkbox" checked={style} onChange={(e) => setStyle(e.target.checked)} /> {t.noirStyle}</label>
        <label><input type="checkbox" checked={hatch} onChange={(e) => setHatch(e.target.checked)} /> {t.hatchedData}</label>
        <label><input type="checkbox" checked={adaptive} onChange={(e) => setAdaptive(e.target.checked)} /> {t.adaptiveSize}</label>
      </div>
      <button onClick={encode} disabled={busy || over || text.trim() === ''}>
        {busy ? t.encoding : t.encodeBtn}
      </button>
      {err && <p className="err">{err}</p>}
      {png && (
        <div className="result">
          <img src={png} alt="NoiR Code panel" />
          <a href={png} download="noircode.png">{t.downloadPng}</a>
        </div>
      )}
    </section>
  )
}

// POST an image blob to the decode endpoint. Throws on HTTP error.
async function postDecode(blob: Blob): Promise<DecodeResult> {
  const fd = new FormData()
  fd.append('image', blob, 'capture.jpg')
  const res = await fetch(`${API}/decode`, { method: 'POST', body: fd })
  if (!res.ok) throw new Error(await errorDetail(res))
  return (await res.json()) as DecodeResult
}

function ResultView({ result, t }: { result: DecodeResult; t: Dict }) {
  if (!result.ok) return <p className="err">{t.couldNotDecode(result.failed_stage)}</p>
  return (
    <div className="decoded">
      <p className="text">{result.text}</p>
      <dl>
        <div><dt>{t.confidence}</dt><dd>{(result.confidence * 100).toFixed(1)}%</dd></div>
        <div><dt>{t.rotation}</dt><dd>{result.rotation}°</dd></div>
        <div><dt>{t.gridErasures}</dt><dd>{result.grid_erasures}</dd></div>
        <div><dt>{t.crossCheck}</dt><dd>{String(result.cross_check)}</dd></div>
      </dl>
    </div>
  )
}

function Decoder({ t }: { t: Dict }) {
  const [mode, setMode] = useState<'upload' | 'camera'>('upload')
  const [result, setResult] = useState<DecodeResult | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const [scanning, setScanning] = useState(false)
  const [facing, setFacing] = useState<'environment' | 'user'>('environment')
  const [torchSupported, setTorchSupported] = useState(false)
  const [torchOn, setTorchOn] = useState(false)

  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((tr) => tr.stop())
    streamRef.current = null
    setScanning(false)
    setTorchSupported(false)
    setTorchOn(false)
  }, [])

  // Torch (flashlight) is a non-standard MediaTrack constraint; gate on capability.
  const toggleTorch = useCallback(async () => {
    const track = streamRef.current?.getVideoTracks()[0]
    if (!track) return
    const next = !torchOn
    try {
      await track.applyConstraints({ advanced: [{ torch: next }] } as unknown as MediaTrackConstraints)
      setTorchOn(next)
    } catch {
      setTorchSupported(false)
    }
  }, [torchOn])

  async function decodeFile(file: File) {
    setErr(null)
    setResult(null)
    setBusy(true)
    setPreview((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return URL.createObjectURL(file)
    })
    try {
      setResult(await postDecode(file))
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  // Start/stop the camera stream when entering/leaving camera mode (or flipping).
  useEffect(() => {
    if (mode !== 'camera') {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      stopCamera()
      return
    }
    let cancelled = false
    setErr(null)
    setResult(null)
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: facing }, audio: false })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((tr) => tr.stop())
          return
        }
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
        }
        const track = stream.getVideoTracks()[0]
        const caps = track?.getCapabilities?.() as { torch?: boolean } | undefined
        setTorchSupported(Boolean(caps && 'torch' in caps))
        setScanning(true)
      })
      .catch((e) => {
        setErr(e instanceof Error && e.name === 'NotAllowedError' ? t.camDenied : t.camUnavailable)
      })
    return () => {
      cancelled = true
      stopCamera()
    }
  }, [mode, facing, stopCamera, t])

  // Grab a frame every ~400ms and try to decode it; stop on success.
  useEffect(() => {
    if (!scanning) return
    let active = true
    let inFlight = false
    const tick = async () => {
      const video = videoRef.current
      const canvas = canvasRef.current
      if (inFlight || !active || !video || !canvas || video.readyState < 2) return
      inFlight = true
      try {
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        canvas.getContext('2d')?.drawImage(video, 0, 0)
        const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, 'image/jpeg', 0.92))
        if (!active || !blob) return
        const res = await postDecode(blob)
        if (active && res.ok) {
          setResult(res)
          stopCamera()
        }
      } catch {
        /* keep scanning on transient errors */
      } finally {
        inFlight = false
      }
    }
    const id = setInterval(tick, 400)
    return () => {
      active = false
      clearInterval(id)
    }
  }, [scanning, stopCamera])

  return (
    <section className="panel">
      <h2>{t.decode}</h2>
      <div className="tabs">
        <button className={mode === 'upload' ? 'tab active' : 'tab'} onClick={() => setMode('upload')}>
          {t.upload}
        </button>
        <button className={mode === 'camera' ? 'tab active' : 'tab'} onClick={() => setMode('camera')}>
          {t.scanCamera}
        </button>
      </div>

      {mode === 'upload' && (
        <input
          type="file"
          accept="image/*"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) decodeFile(f)
          }}
        />
      )}

      {mode === 'camera' && (
        <div className="scanner">
          <video ref={videoRef} autoPlay playsInline muted />
          <canvas ref={canvasRef} hidden />
          <div className="cam-controls">
            <span className="hint">{scanning ? t.pointAtPanel : t.startingCamera}</span>
            <div className="cam-buttons">
              {torchSupported && (
                <button className={torchOn ? 'tab active' : 'tab'} onClick={toggleTorch}>
                  {t.torch}
                </button>
              )}
              <button
                className="tab"
                onClick={() => setFacing((f) => (f === 'environment' ? 'user' : 'environment'))}
              >
                {t.flip}
              </button>
            </div>
          </div>
        </div>
      )}

      {busy && <p>{t.decoding}</p>}
      {err && <p className="err">{err}</p>}
      {mode === 'upload' && preview && (
        <div className="result">
          <img src={preview} alt="uploaded panel" />
        </div>
      )}
      {result && <ResultView result={result} t={t} />}
    </section>
  )
}

export default function App() {
  const [lang, setLang] = useState<Lang>(loadLang)
  const t = I18N[lang]

  useEffect(() => {
    document.documentElement.lang = lang
    saveLang(lang)
  }, [lang])

  return (
    <main>
      <header>
        <div className="topbar">
          <h1>NoiR Code</h1>
          <div className="lang">
            <button className={lang === 'en' ? 'tab active' : 'tab'} onClick={() => setLang('en')}>
              EN
            </button>
            <button className={lang === 'ru' ? 'tab active' : 'tab'} onClick={() => setLang('ru')}>
              RU
            </button>
          </div>
        </div>
        <p>
          {t.sloganPre}
          <em>{t.sloganEm}</em>
          {t.sloganPost}
        </p>
      </header>
      <div className="grid">
        <Encoder t={t} />
        <Decoder t={t} />
      </div>
    </main>
  )
}
