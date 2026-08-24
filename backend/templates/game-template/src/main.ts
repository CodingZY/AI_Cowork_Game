import Phaser from 'phaser'

// game-template minimal Phaser entry (Phase 3: only main.ts in template src/)
// code-generator will create src/scenes/* and wire them here via the Integration contract.
// Until then, an inline placeholder scene keeps the build green.
new Phaser.Game({
  type: Phaser.AUTO,
  parent: 'game',
  width: 800,
  height: 600,
  pixelArt: true,
  scene: {
    key: 'Placeholder',
    create(this: Phaser.Scene) {
      this.add.text(16, 16, 'Game not implemented yet.', { fontSize: '16px', color: '#ffffff' })
    },
  },
})
