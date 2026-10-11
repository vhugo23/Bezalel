import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./e2e',timeout:90000,use:{baseURL:'http://127.0.0.1:5173',viewport:{width:1440,height:1000},trace:'retain-on-failure'},workers:1});
