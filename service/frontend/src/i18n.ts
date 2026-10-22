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
  aboutTitle: string
  aboutLead: string
  aboutBody: string
  aboutPoints: string[]
  aboutMore: string
  howItWorks: string
  howItWorksHref: string
  sourceCode: string
  madeBy: string
  upload: string
  scanCamera: string
  fromUrl: string
  urlPlaceholder: string
  invalidUrl: string
  decodeUrlBtn: string
  pointAtPanel: string
  startingCamera: string
  flip: string
  torch: string
  tapToFocus: string
  holdSteady: string
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
  aboutTitle: 'What is NoiR Code?',
  aboutLead: 'A QR code that is also a noir comic panel.',
  aboutBody:
    'NoiR Code turns a short message or a link into a picture of a rain-soaked city at night. The picture is the code: the shades of its shadows carry your words, and the decoder on this page reads them back from a photo, a screenshot or your camera.',
  aboutPoints: [
    'Up to about 170 letters of text, or a link, in one panel.',
    'Reads from phone photos and screenshots, even tilted or upside down.',
    'Built-in repair data rebuilds parts lost to glare, blur or a crease.',
    'Free, and open source.',
  ],
  aboutMore: 'How NoiR Code works →',
  howItWorks: 'How it works',
  howItWorksHref: '/how-it-works',
  sourceCode: 'Source code ↗',
  madeBy: 'suncake.xyz ↗',
  upload: 'Upload',
  scanCamera: 'Scan camera',
  fromUrl: 'From URL',
  urlPlaceholder: 'https://example.com/panel.png',
  invalidUrl: 'Enter a valid HTTP or HTTPS URL',
  decodeUrlBtn: 'Decode',
  pointAtPanel: 'Point at a panel…',
  startingCamera: 'Starting camera…',
  flip: 'Flip',
  torch: 'Torch',
  tapToFocus: 'Tap to focus',
  holdSteady: 'Hold steady…',
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
  aboutTitle: 'Что такое NoiR Code?',
  aboutLead: 'QR-код, который выглядит как кадр нуарного комикса.',
  aboutBody:
    'NoiR Code превращает короткое послание или ссылку в картинку ночного города под дождём. Картинка и есть код: оттенки её теней несут твои слова, а декодер на этой странице прочитает их обратно с фото, скриншота или камеры.',
  aboutPoints: [
    'До 170 латинских или около 85 русских букв, либо ссылка, в одной панели.',
    'Читается с фото и скриншотов, даже под углом или вверх ногами.',
    'Встроенные данные для восстановления спасают то, что скрыли блик, размытие или сгиб.',
    'Бесплатно, с открытым исходным кодом.',
  ],
  aboutMore: 'Как работает NoiR Code →',
  howItWorks: 'Как это работает',
  howItWorksHref: '/ru/how-it-works',
  sourceCode: 'Исходный код ↗',
  madeBy: 'suncake.xyz ↗',
  upload: 'Загрузить',
  scanCamera: 'Сканировать',
  fromUrl: 'По ссылке',
  urlPlaceholder: 'https://example.com/panel.png',
  invalidUrl: 'Введите корректный URL с HTTP или HTTPS',
  decodeUrlBtn: 'Декодировать',
  pointAtPanel: 'Наведите на панель…',
  startingCamera: 'Запуск камеры…',
  flip: 'Перевернуть',
  torch: 'Фонарик',
  tapToFocus: 'Нажмите для фокуса',
  holdSteady: 'Держите ровно…',
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
