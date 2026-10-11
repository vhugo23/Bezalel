import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./e2e',timeout:180000,expect:{timeout:20000},use:{baseURL:process.env.PREPCREW_E2E_ORIGIN||'http://127.0.0.1:15173',viewport:{width:1440,height:1000},trace:'retain-on-failure'},workers:1,reporter:'list'});
