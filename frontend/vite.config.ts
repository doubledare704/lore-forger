import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			// Dev convenience: call backend from the frontend using same-origin paths.
			// This avoids CORS issues during local development.
			'/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
			'/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
			'/presentations': { target: 'http://127.0.0.1:8000', changeOrigin: true }
		}
	}
});
