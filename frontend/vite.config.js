import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	// Fix dependency optimization issues
	optimizeDeps: {
		exclude: ['clsx']
	},
	// Clear the cache on startup
	server: {
		fs: {
			strict: true,
		},
		hmr: {
			overlay: false
		}
	}
}); 