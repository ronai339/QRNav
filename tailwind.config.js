/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./src/**/*.{js,html}",     // source JS, needed?
    "./templates/**/*.html",    // all the Flask templates!
    "./static/**/*.{js,css}"    // for dynamic classes
  ],
  theme: { extend: {} },
  plugins: [],
}
