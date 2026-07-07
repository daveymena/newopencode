import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import { execSync } from 'child_process';
import { existsSync } from 'fs';

puppeteer.use(StealthPlugin());

const CHROME_PATHS = {
  win32: [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    `${process.env.LOCALAPPDATA}\\Google\\Chrome\\Application\\chrome.exe`,
  ],
  linux: [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium-browser',
    '/usr/bin/chromium',
    '/snap/bin/chromium',
  ],
  darwin: [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    `${process.env.HOME}/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`,
  ],
};

function findChrome() {
  const platform = process.platform;
  const paths = CHROME_PATHS[platform] || [];
  for (const p of paths) {
    if (existsSync(p)) return p;
  }
  try {
    const result = execSync(platform === 'win32'
      ? 'where chrome'
      : 'which google-chrome || which chromium-browser || which chromium',
      { encoding: 'utf-8' });
    const line = result.split('\n')[0].trim();
    if (line) return line;
  } catch {}
  return null;
}

export class BrowserManager {
  constructor(options = {}) {
    this.headless = options.headless !== false;
    this.userDataDir = options.userDataDir || null;
    this.proxy = options.proxy || null;
    this.viewport = options.viewport || { width: 1280, height: 800 };
    this.browser = null;
    this.page = null;
  }

  async launch() {
    const chromePath = findChrome();
    if (!chromePath) {
      console.log('  [Browser] Chrome no encontrado, instalando chromium...');
    }

    const args = [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--disable-web-security',
      '--disable-features=IsolateOrigins,site-per-process',
      '--window-size=1280,800',
      '--start-maximized',
      '--lang=en-US',
      '--disable-blink-features=AutomationControlled',
      '--disable-infobars',
      '--disable-notifications',
    ];

    if (this.proxy) {
      args.push(`--proxy-server=${this.proxy}`);
    }

    if (this.userDataDir) {
      args.push(`--user-data-dir=${this.userDataDir}`);
    }

    this.browser = await puppeteer.launch({
      executablePath: chromePath,
      headless: this.headless ? 'new' : false,
      args,
      defaultViewport: null,
      ignoreHTTPSErrors: true,
    });

    const pages = await this.browser.pages();
    this.page = pages[0] || await this.browser.newPage();

    await this.page.setViewport(this.viewport);

    await this.page.evaluateOnNewDocument(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => false });
      Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
      Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
      Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
      Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
    });

    console.log(`  [Browser] Chrome lanzado (headless: ${this.headless})`);
    return { browser: this.browser, page: this.page };
  }

  async navigate(url) {
    if (!this.page) throw new Error('Browser not launched');
    console.log(`  [Browser] Navegando a: ${url}`);
    await this.page.goto(url, {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });
    await this.delay(1000);
  }

  async getPageInfo() {
    if (!this.page) return { url: '', title: '' };
    try {
      return {
        url: this.page.url(),
        title: await this.page.title(),
      };
    } catch {
      return { url: '', title: '' };
    }
  }

  async takeScreenshot() {
    if (!this.page) return null;
    return await this.page.screenshot({ encoding: 'base64', type: 'png' });
  }

  async clickElement(text) {
    if (!this.page) return false;
    for (let attempt = 0; attempt < 8; attempt++) {
      try {
        const clicked = await this.page.evaluate((txt) => {
          const selectors = [
            `button:has-text("${txt}")`,
            `a:has-text("${txt}")`,
            `input[value="${txt}"]`,
            `[role="button"]:has-text("${txt}")`,
            `[role="link"]:has-text("${txt}")`,
            `[role="option"]:has-text("${txt}")`,
            `span:has-text("${txt}")`,
            `label:has-text("${txt}")`,
            `[aria-label="${txt}"]`,
            `[title="${txt}"]`,
            `[placeholder="${txt}"]`,
            `div:has-text("${txt}")`,
          ];

          for (const sel of selectors) {
            try {
              const el = document.querySelector(sel);
              if (el && el.offsetParent !== null) {
                el.scrollIntoView({ block: 'center', behavior: 'instant' });
                el.click();
                return true;
              }
            } catch {}
          }

          const allElements = document.querySelectorAll('button, a, input[type="submit"], input[type="button"], [role="button"], [role="link"], span, label, div, li, td');
          for (const el of allElements) {
            const elText = (el.innerText || el.textContent || el.value || '').trim().toLowerCase();
            const searchText = txt.toLowerCase();
            if (elText === searchText || elText.includes(searchText)) {
              if (el.offsetParent !== null) {
                el.scrollIntoView({ block: 'center', behavior: 'instant' });
                el.click();
                return true;
              }
            }
          }
          return false;
        }, text);

        if (clicked) {
          await this.delay(500);
          return true;
        }
      } catch {}
      await this.delay(500);
    }
    return false;
  }

  async typeText(text, fieldIdentifier) {
    if (!this.page) return false;
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        const typed = await this.page.evaluate(([txt, fieldId]) => {
          const fieldIdLower = fieldId.toLowerCase();

          const selectors = [
            `input[type="text"][placeholder*="${fieldId}" i]`,
            `input[type="email"][placeholder*="${fieldId}" i]`,
            `input[type="password"][placeholder*="${fieldId}" i]`,
            `input[type="search"][placeholder*="${fieldId}" i]`,
            `input[type="tel"][placeholder*="${fieldId}" i]`,
            `input[type="url"][placeholder*="${fieldId}" i]`,
            `textarea[placeholder*="${fieldId}" i]`,
            `input[aria-label*="${fieldId}" i]`,
            `textarea[aria-label*="${fieldId}" i]`,
            `input[name*="${fieldId}" i]`,
            `textarea[name*="${fieldId}" i]`,
            `input[id*="${fieldId}" i]`,
            `textarea[id*="${fieldId}" i]`,
          ];

          for (const sel of selectors) {
            try {
              const el = document.querySelector(sel);
              if (el && el.offsetParent !== null) {
                el.scrollIntoView({ block: 'center' });
                el.focus();
                el.value = '';
                el.value = txt;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur'));
                return true;
              }
            } catch {}
          }

          const allInputs = document.querySelectorAll('input, textarea');
          for (const inp of allInputs) {
            const labels = [];
            const label = document.querySelector(`label[for="${inp.id}"]`);
            if (label) labels.push(label.textContent.trim().toLowerCase());

            const parent = inp.closest('div, fieldset, section');
            if (parent) {
              const parentLabel = parent.querySelector('label, span, strong, b, p');
              if (parentLabel) labels.push(parentLabel.textContent.trim().toLowerCase());
            }

            const ph = (inp.placeholder || '').toLowerCase();
            const name = (inp.name || '').toLowerCase();
            const id = (inp.id || '').toLowerCase();
            const aria = (inp.getAttribute('aria-label') || '').toLowerCase();

            const allText = [...labels, ph, name, id, aria].join(' ');
            if (allText.includes(fieldIdLower)) {
              inp.scrollIntoView({ block: 'center' });
              inp.focus();
              inp.value = '';
              inp.value = txt;
              inp.dispatchEvent(new Event('input', { bubbles: true }));
              inp.dispatchEvent(new Event('change', { bubbles: true }));
              inp.dispatchEvent(new Event('blur'));
              return true;
            }
          }
          return false;
        }, [text, fieldIdentifier]);

        if (typed) {
          await this.delay(300);
          return true;
        }
      } catch {}
      await this.delay(500);
    }

    // Fallback: type character by character using keyboard
    try {
      await this.page.keyboard.type(text, { delay: 50 });
      return true;
    } catch {
      return false;
    }
  }

  async selectOption(optionText, dropdownIdentifier) {
    if (!this.page) return false;
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        const selected = await this.page.evaluate(([opt, fieldId]) => {
          const fieldIdLower = fieldId.toLowerCase();
          const optLower = opt.toLowerCase();

          const selects = document.querySelectorAll('select');
          for (const sel of selects) {
            const labels = [];
            const label = document.querySelector(`label[for="${sel.id}"]`);
            if (label) labels.push(label.textContent.trim().toLowerCase());
            const name = (sel.name || '').toLowerCase();
            const id = (sel.id || '').toLowerCase();
            const allText = [...labels, name, id].join(' ');
            if (allText.includes(fieldIdLower)) {
              for (const option of sel.options) {
                if (option.text.toLowerCase().includes(optLower) || option.value.toLowerCase().includes(optLower)) {
                  sel.value = option.value;
                  sel.dispatchEvent(new Event('change', { bubbles: true }));
                  return true;
                }
              }
            }
          }
          return false;
        }, [optionText, dropdownIdentifier]);

        if (selected) {
          await this.delay(300);
          return true;
        }
      } catch {}
      await this.delay(500);
    }
    return false;
  }

  async scroll(direction = 'down') {
    if (!this.page) return;
    const amount = direction === 'down' ? 500 : -500;
    await this.page.evaluate((amt) => {
      window.scrollBy({ top: amt, left: 0, behavior: 'smooth' });
    }, amount);
    await this.delay(500);
  }

  async extractText() {
    if (!this.page) return '';
    try {
      return await this.page.evaluate(() => document.body.innerText);
    } catch {
      return '';
    }
  }

  async waitForPageLoad() {
    if (!this.page) return;
    try {
      await this.page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 15000 });
    } catch {}
    await this.delay(2000);
  }

  async screenshotElement(selector) {
    if (!this.page) return null;
    try {
      const el = await this.page.$(selector);
      if (el) return await el.screenshot({ encoding: 'base64' });
    } catch {}
    return null;
  }

  async close() {
    if (this.browser) {
      try { await this.browser.close(); } catch {}
      this.browser = null;
      this.page = null;
    }
  }

  delay(ms) {
    return new Promise(r => setTimeout(r, ms + Math.random() * 50));
  }
}
