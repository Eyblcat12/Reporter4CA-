/* global __dirname */
module.exports = {
  content: [require('node:path').join(__dirname, 'stitch-reference.html')],
  theme: { extend: {
    fontFamily: { sans: ['Be Vietnam Pro', 'Inter', 'Segoe UI', 'sans-serif'], mono: ['JetBrains Mono', 'Consolas', 'monospace'] },
    boxShadow: { subtle: '0 1px 2px 0 rgb(0 0 0 / 0.04)', paper: '0 0 0 1px rgb(226 232 240 / 0.8), 0 8px 24px -4px rgb(15 23 42 / 0.06)' }
  } }
};
