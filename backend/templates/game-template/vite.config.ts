import { defineConfig } from 'vite'
import { cpSync, mkdirSync, rmSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * closeBundle 插件：build 末尾把 assets/final 拷到 dist/assets/final。
 * Phaser load.image 用相对路径 'assets/final/...'，png 运行时加载需随 dist 部署。
 * 放 vite 进程内（closeBundle 钩子）而非 build 后的额外 npm 脚本命令——
 * 避免 npm/node segfault 在 `&&` 链中中断导致拷贝未执行。
 */
function copyAssetsPlugin() {
  return {
    name: 'copy-assets-final',
    closeBundle() {
      const root = process.cwd()
      const src = resolve(root, 'assets/final')
      const dest = resolve(root, 'dist/assets/final')
      if (!existsSync(src)) {
        console.warn('[copy-assets] assets/final 不存在，跳过')
        return
      }
      if (existsSync(dest)) rmSync(dest, { recursive: true, force: true })
      mkdirSync(resolve(dest, '..'), { recursive: true })
      cpSync(src, dest, { recursive: true })
      console.log(`[copy-assets] ${src} → ${dest}`)
    },
  }
}

export default defineConfig({
  // 部署在子路径 /play/{key}/{version}/dist/ 下；base:'./' 避免绝对路径 404 黑屏
  base: './',
  server: { port: 5173 },
  build: { outDir: 'dist' },
  plugins: [copyAssetsPlugin()],
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
