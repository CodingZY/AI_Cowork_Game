// game-template canvas skeleton (spec §108: TS/Vite/Canvas)
const canvas = document.getElementById('game') as HTMLCanvasElement
const ctx = canvas.getContext('2d')!

function loop() {
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  requestAnimationFrame(loop)
}

loop()
