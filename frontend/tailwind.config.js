/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        serif: ["'Noto Serif SC'", "Georgia", "serif"],
      },
      boxShadow: {
        card: "0 8px 30px rgb(0,0,0,0.04)",
        "card-hover": "0 20px 40px rgb(0,0,0,0.06)",
      },
      keyframes: {
        shimmer: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
        "complete-flash": {
          "0%, 100%": { backgroundColor: "rgb(255,255,255,0.8)" },
          "50%": { backgroundColor: "rgba(16,185,129,0.15)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.5s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
