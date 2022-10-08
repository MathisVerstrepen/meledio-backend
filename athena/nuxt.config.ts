import { defineNuxtConfig } from "nuxt";

// https://v3.nuxtjs.org/api/configuration/nuxt.config
export default defineNuxtConfig({
  css: ["~/assets/css/tailwind.css"],
  // buildModules: ["@nuxt/postcss8", "@nuxtjs/eslint-module", "@nuxt/typescript-build"],
  postcss: {
    plugins: {
      tailwindcss: {},
      autoprefixer: {},
    },
  },
});
