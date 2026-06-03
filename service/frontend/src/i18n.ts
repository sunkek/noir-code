// Minimal two-locale dictionary. No i18n library — the app is small enough that a
// typed record + a localStorage-backed toggle is the whole feature.

export type Lang = 'en' | 'ru'

export type Dict = {
  sloganPre: string
  sloganEm: string
  sloganPost: string
  encode: string
  decode: string
  noirStyle: string
  hatchedData: string
  adaptiveSize: string
  caption: string
  bytes: (n: number, max: number) => string
  textPlaceholder: string
  encodeBtn: string
  encoding: string
  downloadPng: string
  sourceCode: string
  upload: string
  scanCamera: string
  fromUrl: string
  urlPlaceholder: string
  decodeUrlBtn: string
  pointAtPanel: string
  startingCamera: string
  flip: string
  torch: string
  decoding: string
  couldNotDecode: (stage: string | null) => string
  confidence: string
  rotation: string
  gridErasures: string
  crossCheck: string
  camDenied: string
  camUnavailable: string
}

const en: Dict = {
  sloganPre: 'Your message, hidden in the shadows of a ',
  sloganEm: 'nocturnal city of rain',
  sloganPost: '.',
  encode: 'Encode',
  decode: 'Decode',
  noirStyle: 'Noir style',
  hatchedData: 'Hatched data',
  adaptiveSize: 'Adaptive size',
  caption: 'Caption',
  bytes: (n, max) => `${n} / ${max} bytes`,
  textPlaceholder: 'Text to encode…',
  encodeBtn: 'Encode',
  encoding: 'Encoding…',
  downloadPng: 'Download PNG',
  sourceCode: 'Source code ↗',
  upload: 'Upload',
  scanCamera: 'Scan camera',
  fromUrl: 'From URL',
  urlPlaceholder: 'https://example.com/panel.png',
  decodeUrlBtn: 'Decode',
  pointAtPanel: 'Point at a panel…',
  startingCamera: 'Starting camera…',
  flip: 'Flip',
  torch: 'Torch',
  decoding: 'Decoding…',
  couldNotDecode: (stage) => `Could not decode: ${stage}`,
  confidence: 'confidence',
  rotation: 'rotation',
  gridErasures: 'grid erasures',
  crossCheck: 'cross-check',
  camDenied: 'Camera permission denied',
  camUnavailable: 'Camera unavailable (needs HTTPS, or no camera found)',
}

const ru: Dict = {
  sloganPre: 'Твоё послание, сокрытое в тенях ',
  sloganEm: 'ночного города дождя',
  sloganPost: '.',
  encode: 'Кодировать',
  decode: 'Декодировать',
  noirStyle: 'Нуар-стиль',
  hatchedData: 'Штриховка данных',
  adaptiveSize: 'Адаптивный размер',
  caption: 'Подпись',
  bytes: (n, max) => `${n} / ${max} байт`,
  textPlaceholder: 'Текст для кодирования…',
  encodeBtn: 'Кодировать',
  encoding: 'Кодирую…',
  downloadPng: 'Скачать PNG',
  sourceCode: 'Исходный код ↗',
  upload: 'Загрузить',
  scanCamera: 'Сканировать',
  fromUrl: 'По ссылке',
  urlPlaceholder: 'https://example.com/panel.png',
  decodeUrlBtn: 'Декодировать',
  pointAtPanel: 'Наведите на панель…',
  startingCamera: 'Запуск камеры…',
  flip: 'Перевернуть',
  torch: 'Фонарик',
  decoding: 'Декодирую…',
  couldNotDecode: (stage) => `Не удалось декодировать: ${stage}`,
  confidence: 'достоверность',
  rotation: 'поворот',
  gridErasures: 'стёртые ячейки',
  crossCheck: 'перекрёстная проверка',
  camDenied: 'Доступ к камере запрещён',
  camUnavailable: 'Камера недоступна (нужен HTTPS или камера не найдена)',
}

export const I18N: Record<Lang, Dict> = { en, ru }

export function loadLang(): Lang {
  const v = typeof localStorage !== 'undefined' ? localStorage.getItem('lang') : null
  return v === 'ru' ? 'ru' : 'en'
}

export function saveLang(lang: Lang): void {
  try {
    localStorage.setItem('lang', lang)
  } catch {
    /* ignore storage errors (private mode etc.) */
  }
}
