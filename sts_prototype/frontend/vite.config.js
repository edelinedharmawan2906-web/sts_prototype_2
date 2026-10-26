import { defineConfig } from 'vite';
export default defineConfig({base:'/camera/',worker:{format:'iife'},server:{proxy:{'/history':'http://127.0.0.1:8000','/sessions':'http://127.0.0.1:8000','/health':'http://127.0.0.1:8000'}}});
