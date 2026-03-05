<script lang="ts">
 	import { onMount } from 'svelte';
 	import WorldStateSidebar from './WorldStateSidebar.svelte';

	type LogItem =
		| { id: string; type: 'text'; role: 'user' | 'assistant' | 'system'; content: string }
		| { id: string; type: 'image'; role: 'assistant'; url: string; alt: string }
		| { id: string; type: 'audio'; role: 'assistant'; url: string; mimeType?: string };

	type StreamEvent =
		| { type: 'meta'; model?: string; session_id?: string | null }
		| { type: 'text'; delta: string }
		| { type: 'image'; url: string; alt?: string }
		| { type: 'audio'; url: string; mime_type?: string }
		| { type: 'error'; message: string }
		| { type: 'done' };

	let prompt = $state('');
	let isSending = $state(false);
	let isGeneratingDeck = $state(false);
		let sessionId = $state<string | null>(null);
			let showDecks = $state(false);
			let decks = $state<
				{ presentation_id: string; url: string; title: string; created_at?: string | null }[]
			>([]);
			let isLoadingDecks = $state(false);
			let decksError = $state<string | null>(null);
	interface WorldState {
		campaign?: {
			title: string;
			premise: string;
			tone: string;
		};
		locations?: Array<{
			name: string;
			description: string;
			tags: string[];
		}>;
		npcs?: Array<{
			name: string;
			role: string;
			description: string;
			location: string;
		}>;
		quests?: Array<{
			name: string;
			status: string;
			summary: string;
		}>;
	}

	interface InventoryItem {
		name: string;
		qty: number;
		description?: string;
	}

	let model = $state<string | null>(null);
	let lastError = $state<string | null>(null);

	let worldState = $state<WorldState | null>(null);
	let inventory = $state<InventoryItem[]>([]);
	let showSidebar = $state(false);

	let abortController = $state<AbortController | null>(null);
	let streamEl: HTMLDivElement | null = null;
		let sessionInitPromise: Promise<string | null> | null = null;

	let log = $state<LogItem[]>([
		{
			id: crypto.randomUUID(),
			type: 'text',
			role: 'system',
			content:
				'LoreForge ready. This grimoire now streams from the FastAPI SSE endpoint (/api/stream).'
		}
	]);

	$effect(() => {
		// Auto-scroll whenever the latest item changes (including text deltas).
		const last = log.at(-1);
		if (last?.type === 'text') {
			void last.content;
		}
		queueMicrotask(() => {
			streamEl?.scrollTo({ top: streamEl.scrollHeight, behavior: 'smooth' });
		});
	});

	function clear() {
		log = [
			{
				id: crypto.randomUUID(),
				type: 'text',
				role: 'system',
				content: 'Cleared. The grimoire awaits a new incantation.'
			}
		];
		lastError = null;
	}

	async function* parseSseJson(res: Response): AsyncGenerator<StreamEvent, void, void> {
		if (!res.body) return;

		const reader = res.body.getReader();
		const decoder = new TextDecoder();
		let buffer = '';

		while (true) {
			const { value, done } = await reader.read();
			if (done) break;

			buffer += decoder.decode(value, { stream: true });

			// SSE events are separated by a blank line.
			while (true) {
				const sepIndex = buffer.indexOf('\n\n');
				if (sepIndex === -1) break;

				const rawEvent = buffer.slice(0, sepIndex).replaceAll('\r', '');
				buffer = buffer.slice(sepIndex + 2);

				for (const line of rawEvent.split('\n')) {
					if (!line.startsWith('data:')) continue;
					const jsonStr = line.replace(/^data:\s?/, '');
					if (!jsonStr) continue;
					try {
						yield JSON.parse(jsonStr) as StreamEvent;
					} catch {
						// ignore malformed chunk
					}
				}
			}
		}
	}

	function stop() {
		abortController?.abort();
		abortController = null;
		isSending = false;
	}

		function shortSession(id: string | null): string {
			if (!id) return '—';
			return id.length <= 12 ? id : `${id.slice(0, 8)}…`;
		}

		async function copySessionId() {
			if (!sessionId) return;
			try {
				await navigator.clipboard.writeText(sessionId);
				log.push({
					id: crypto.randomUUID(),
					type: 'text',
					role: 'system',
					content: `Copied session_id: ${sessionId}`
				});
			} catch (e) {
				log.push({
					id: crypto.randomUUID(),
					type: 'text',
					role: 'system',
					content: `Error: failed to copy session_id: ${(e as Error).message}`
				});
			}
		}

		async function startNewSession() {
			try {
					// Cancel any pending auto-derive scheduled for the old session.
					if (deriveTimer) {
						clearTimeout(deriveTimer);
						deriveTimer = null;
					}
					pendingDeriveSid = null;
					lastDeriveAtMs = 0;

				localStorage.removeItem('loreforge_session_id');
				sessionId = null;
					showDecks = false;
					decks = [];
					decksError = null;
				sessionInitPromise = null;
				clear();
				const sid = await ensureSessionId();
				log.push({
					id: crypto.randomUUID(),
					type: 'text',
					role: 'system',
					content: sid ? `New session started: ${sid}` : 'New session: failed to initialize.'
				});
			} catch (e) {
				log.push({
					id: crypto.randomUUID(),
					type: 'text',
					role: 'system',
					content: `Error: failed to start new session: ${(e as Error).message}`
				});
			}
		}

		function downloadJson(filename: string, data: unknown) {
			const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = filename;
			document.body.appendChild(a);
			a.click();
			a.remove();
			URL.revokeObjectURL(url);
		}

		async function exportSessionEvents() {
			const sid = await ensureSessionId();
			if (!sid) return;
			try {
				const res = await fetch(`/api/sessions/${sid}/events?limit=200`, {
					headers: { Accept: 'application/json' }
				});
				if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
				const data = await res.json();
				downloadJson(`loreforge-session-${sid}-events.json`, data);
				log.push({
					id: crypto.randomUUID(),
					type: 'text',
					role: 'system',
					content: `Exported events for session: ${sid}`
				});
			} catch (e) {
				log.push({
					id: crypto.randomUUID(),
					type: 'text',
					role: 'system',
					content: `Error: failed to export events: ${(e as Error).message}`
				});
			}
		}

		async function initSession(): Promise<string | null> {
			try {
				const existing = localStorage.getItem('loreforge_session_id');
				if (existing) {
					sessionId = existing;
					void refreshSessionState(existing);
					return existing;
				}

				const res = await fetch('/api/sessions', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
					body: JSON.stringify({})
				});
				if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
				const data = (await res.json()) as { session_id: string };
				sessionId = data.session_id;
				localStorage.setItem('loreforge_session_id', data.session_id);
				return data.session_id;
			} catch (e) {
				lastError = (e as Error).message;
				log.push({
					id: crypto.randomUUID(),
					type: 'text',
					role: 'system',
					content: `Error: failed to create session: ${(e as Error).message}`
				});
				return null;
			}
		}

		async function ensureSessionId(): Promise<string | null> {
			if (sessionId) return sessionId;
			sessionInitPromise ??= initSession();
			return await sessionInitPromise;
		}

		async function addSessionEvent(role: string, content: string, kind = 'text') {
			const sid = await ensureSessionId();
			if (!sid) return;
			try {
				await fetch(`/api/sessions/${sid}/events`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
					body: JSON.stringify({ role, content, kind })
				});
			} catch {
				// best-effort only
			}
		}

			// Auto-derive throttling: keep it automatic, but avoid calling Gemini on every
			// assistant response if responses happen in quick succession.
			const DERIVE_MIN_INTERVAL_MS = 15_000;
			let deriveInFlight = false;
			let lastDeriveAtMs = 0;
			let deriveTimer: ReturnType<typeof setTimeout> | null = null;
			let pendingDeriveSid: string | null = null;

			async function deriveSessionState(sid: string) {
				deriveInFlight = true;
				try {
					const res = await fetch(`/api/sessions/${sid}/state/derive`, {
						method: 'POST',
						headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
						body: JSON.stringify({ events_limit: 50 })
					});
					if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
					const data = await res.json();
					worldState = data.world_state;
					inventory = data.inventory;
				} catch (e) {
					log.push({
						id: crypto.randomUUID(),
						type: 'text',
						role: 'system',
						content: `Error: failed to update world_state/inventory: ${(e as Error).message}`
					});
				} finally {
					deriveInFlight = false;
					lastDeriveAtMs = Date.now();
					// If another derive was requested while we were busy, schedule it now.
					if (pendingDeriveSid) requestDeriveSessionState(pendingDeriveSid);
				}
			}

			async function refreshSessionState(sid: string) {
				try {
					const res = await fetch(`/api/sessions/${sid}`, {
						headers: { Accept: 'application/json' }
					});
					if (res.ok) {
						const data = await res.json();
						worldState = data.world_state;
						inventory = data.inventory;
					}
				} catch (e) {
					console.error('[Grimoire] Failed to refresh session state:', e);
				}
			}

			function requestDeriveSessionState(sid: string) {
				pendingDeriveSid = sid;
				if (deriveInFlight) return;
				if (deriveTimer) return;

				const now = Date.now();
				const elapsed = now - lastDeriveAtMs;
				const waitMs = Math.max(0, DERIVE_MIN_INTERVAL_MS - elapsed);
				deriveTimer = setTimeout(() => {
					deriveTimer = null;
					const nextSid = pendingDeriveSid;
					pendingDeriveSid = null;
					if (!nextSid) return;
					void deriveSessionState(nextSid);
				}, waitMs);
			}

		onMount(() => {
			void ensureSessionId();
		});

	function getDeckSourceText(): string | null {
		// Prefer the latest assistant text (so you can generate slides from what was just created).
		for (let i = log.length - 1; i >= 0; i--) {
			const it = log[i];
			if (it.type === 'text' && it.role === 'assistant' && it.content.trim()) {
				return it.content.trim().slice(0, 8000);
			}
		}

		const typed = prompt.trim();
		return typed ? typed.slice(0, 8000) : null;
	}

	async function generateDeck() {
		if (isGeneratingDeck) return;
		lastError = null;
			const sid = await ensureSessionId();
			const focus = prompt.trim();
			const source = getDeckSourceText();
			if (!sid && !source) {
				lastError = 'Nothing to generate from (no session available, and no assistant text yet).';
				log.push({
					id: crypto.randomUUID(),
					type: 'text',
					role: 'system',
					content: `Error: ${lastError}`
				});
				return;
			}

		isGeneratingDeck = true;
		log.push({
			id: crypto.randomUUID(),
			type: 'text',
			role: 'system',
			content: 'Generating presentation deck…'
		});

		try {
				const body: Record<string, unknown> = {};
				if (sid) {
					body.session_id = sid;
					// when session_id is provided, `prompt` is treated as optional focus
					if (focus) body.prompt = focus;
				} else {
					body.prompt = source;
				}

			const res = await fetch('/api/presentations', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Accept: 'application/json'
				},
					body: JSON.stringify(body)
			});

			if (!res.ok) {
				const body = await res.text();
				throw new Error(body || `HTTP ${res.status} ${res.statusText}`);
			}

			const data = (await res.json()) as { url: string; title?: string };
			window.open(data.url, '_blank', 'noopener,noreferrer');
				if (showDecks) void refreshDecks();
			log.push({
				id: crypto.randomUUID(),
				type: 'text',
				role: 'system',
				content: `Opened deck: ${data.title ?? data.url}`
			});
		} catch (e) {
			lastError = (e as Error).message;
			log.push({
				id: crypto.randomUUID(),
				type: 'text',
				role: 'system',
				content: `Error: ${(e as Error).message}`
			});
		} finally {
			isGeneratingDeck = false;
		}
	}

		async function refreshDecks() {
			const sid = await ensureSessionId();
			if (!sid) return;
			isLoadingDecks = true;
			decksError = null;
			try {
				const res = await fetch(
					`/api/presentations?session_id=${encodeURIComponent(sid)}&limit=50`,
					{ headers: { Accept: 'application/json' } }
				);
				if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
				const data = (await res.json()) as {
					presentations?: { presentation_id: string; url: string; title: string; created_at?: string | null }[];
				};
				decks = data.presentations ?? [];
			} catch (e) {
				decksError = (e as Error).message;
			} finally {
				isLoadingDecks = false;
			}
		}

		function toggleDecks() {
			showDecks = !showDecks;
			if (showDecks) void refreshDecks();
		}

		function toggleSidebar() {
			showSidebar = !showSidebar;
		}

	async function send() {
		const text = prompt.trim();
		if (!text || isSending) return;
			const sid = await ensureSessionId();

		isSending = true;
		lastError = null;
		log.push({ id: crypto.randomUUID(), type: 'text', role: 'user', content: text });
			void addSessionEvent('user', text, 'text');
		prompt = '';

		// Assistant message that we will append streamed deltas into.
		const assistantId = crypto.randomUUID();
			let assistantText = '';
		log.push({ id: assistantId, type: 'text', role: 'assistant', content: '' });

		const ctrl = new AbortController();
		abortController = ctrl;

		try {
			const res = await fetch('/api/stream', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Accept: 'text/event-stream'
				},
					body: JSON.stringify({ prompt: text, session_id: sid }),
				signal: ctrl.signal
			});

			if (!res.ok) {
				throw new Error(`HTTP ${res.status} ${res.statusText}`);
			}

			for await (const ev of parseSseJson(res)) {
				if (ev.type === 'meta') {
					model = ev.model ?? model;
						if (ev.session_id && !sessionId) {
							sessionId = ev.session_id;
							localStorage.setItem('loreforge_session_id', ev.session_id);
						}
					continue;
				}

				if (ev.type === 'text') {
						assistantText += ev.delta;
					const idx = log.findIndex((x) => x.id === assistantId);
					if (idx !== -1 && log[idx].type === 'text') {
						(log[idx] as Extract<LogItem, { type: 'text' }>).content += ev.delta;
					}
					continue;
				}

				if (ev.type === 'image') {
					log.push({
						id: crypto.randomUUID(),
						type: 'image',
						role: 'assistant',
						url: ev.url,
						alt: ev.alt ?? 'Generated image'
					});
					continue;
				}

				if (ev.type === 'audio') {
					log.push({
						id: crypto.randomUUID(),
						type: 'audio',
						role: 'assistant',
						url: ev.url,
						mimeType: ev.mime_type
					});
					continue;
				}

				if (ev.type === 'error') {
					lastError = ev.message;
					log.push({
						id: crypto.randomUUID(),
						type: 'text',
						role: 'system',
						content: `Error: ${ev.message}`
					});
					continue;
				}

				if (ev.type === 'done') break;
			}

					if (assistantText.trim()) {
						await addSessionEvent('assistant', assistantText, 'text');
						if (sid) requestDeriveSessionState(sid);
					}
		} catch (e) {
			if ((e as Error).name !== 'AbortError') {
				lastError = (e as Error).message;
				log.push({
					id: crypto.randomUUID(),
					type: 'text',
					role: 'system',
					content: `Error: ${(e as Error).message}`
				});
			}
		} finally {
			abortController = null;
			isSending = false;
		}
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
			e.preventDefault();
			send();
		}
	}
</script>

<div class="panel">
	<div class="panel-header">
		<div>
			<strong>LoreForge Grimoire</strong>
				<div class="hint">
						Ctrl/⌘ + Enter to send • Model: <span class="mono">{model ?? '—'}</span>
						 • Session: <span class="mono">{shortSession(sessionId)}</span>
				</div>
		</div>
			<div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
					<button class="btn secondary" type="button" onclick={copySessionId} disabled={!sessionId}>
						Copy session
					</button>
					<button class="btn secondary" type="button" onclick={startNewSession} disabled={isSending}>
						New session
					</button>
					<button class="btn secondary" type="button" onclick={exportSessionEvents} disabled={!sessionId}>
						Export events
					</button>
					<button class="btn secondary" type="button" onclick={toggleDecks} disabled={!sessionId}>
						{showDecks ? 'Hide decks' : 'My decks'}
					</button>
					<button class="btn secondary" type="button" onclick={toggleSidebar} disabled={!sessionId}>
						{showSidebar ? 'Hide State' : 'World State'}
					</button>
				<button class="btn secondary" type="button" onclick={generateDeck} disabled={isGeneratingDeck}>
					{isGeneratingDeck ? 'Generating…' : 'Generate deck'}
				</button>
				<button class="btn secondary" type="button" onclick={stop} disabled={!isSending}>Stop</button>
				<button class="btn" type="button" onclick={clear} disabled={isSending}>Clear</button>
			</div>
	</div>

		{#if showDecks}
			<div class="deck-panel">
				<div class="deck-panel-header">
					<strong>Decks for this session</strong>
					<button class="btn secondary" type="button" onclick={refreshDecks} disabled={isLoadingDecks}>
						{isLoadingDecks ? 'Refreshing…' : 'Refresh'}
					</button>
				</div>

				{#if decksError}
					<div class="hint mono">Error: {decksError}</div>
				{:else if isLoadingDecks && decks.length === 0}
					<div class="hint mono">Loading…</div>
				{:else if decks.length === 0}
					<div class="hint mono">No decks yet. Click “Generate deck”.</div>
				{:else}
					<ul class="deck-list">
						{#each decks as d (d.presentation_id)}
							<li>
								<button
									class="deck-link"
									type="button"
									onclick={() => window.open(d.url, '_blank', 'noopener,noreferrer')}
								>
									<span class="mono">{d.presentation_id.slice(0, 8)}…</span>
									<span>{d.title}</span>
									{#if d.created_at}
										<span class="hint mono">{d.created_at}</span>
									{/if}
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</div>
		{/if}

	<div class="body" class:has-sidebar={showSidebar}>
		{#if showSidebar}
			<WorldStateSidebar {worldState} {inventory} />
		{/if}
			<div class="stream" aria-label="Streaming output" bind:this={streamEl}>
			{#each log as item (item.id)}
				{#if item.type === 'text'}
					<div class="line {item.role}">
						<span class="tag mono">{item.role}</span>
						<span class="content">{item.content}</span>
					</div>
					{:else if item.type === 'image'}
					<div class="img">
						<img src={item.url} alt={item.alt} />
					</div>
					{:else}
						<div class="audio">
							<audio controls src={item.url}></audio>
							<div class="hint mono">{item.mimeType ?? 'audio'}</div>
						</div>
				{/if}
			{/each}
		</div>

		<div class="composer" aria-label="Prompt input">
			<textarea
				class="input"
				rows="3"
				placeholder="Describe a scene, ask for a faction, request an image..."
				bind:value={prompt}
				onkeydown={onKeydown}
				disabled={isSending}
			></textarea>
			<div class="actions">
				<div class="hint">Tip: ask for “scene + image prompt”.</div>
				<button class="btn" type="button" onclick={send} disabled={isSending || !prompt.trim()}>
					{isSending ? 'Sending…' : 'Send'}
				</button>
			</div>
		</div>
	</div>
</div>

<style>
		.deck-panel {
			border-top: 1px solid rgba(214, 179, 95, 0.25);
			padding: 12px 16px;
			background: rgba(12, 10, 16, 0.22);
		}
		.deck-panel-header {
			display: flex;
			align-items: center;
			justify-content: space-between;
			gap: 12px;
			margin-bottom: 8px;
		}
		.deck-list {
			margin: 8px 0 0;
			padding-left: 18px;
		}
		.deck-link {
			display: flex;
			gap: 10px;
			align-items: baseline;
			width: 100%;
			text-align: left;
			background: transparent;
			border: 0;
			color: inherit;
			padding: 6px 8px;
			border-radius: 10px;
			cursor: pointer;
		}
		.deck-link:hover {
			background: rgba(214, 179, 95, 0.10);
		}

	.body {
		display: grid;
		grid-template-rows: 1fr auto;
		grid-template-columns: 0 1fr;
		min-height: min(72vh, 740px);
		transition: grid-template-columns 0.3s ease;
	}

	.body.has-sidebar {
		grid-template-columns: 320px 1fr;
	}

	.stream {
		grid-column: 2;
		grid-row: 1;
		padding: 16px;
		overflow: auto;
	}

	.line {
		display: grid;
		grid-template-columns: 90px 1fr;
		gap: 10px;
		padding: 10px 0;
		border-bottom: 1px dashed rgba(214, 179, 95, 0.18);
	}

	.tag {
		font-size: 12px;
		color: var(--muted);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		padding-top: 2px;
	}

	.line.user .tag {
		color: var(--accent-2);
	}

	.line.system .tag {
		color: var(--accent);
	}

	.content {
		white-space: pre-wrap;
		line-height: 1.45;
	}

	.img {
		padding: 12px 0 18px;
		border-bottom: 1px dashed rgba(214, 179, 95, 0.18);
	}

	.img img {
		max-width: 100%;
		height: auto;
		border-radius: 12px;
		border: 1px solid rgba(214, 179, 95, 0.28);
		box-shadow: 0 14px 40px rgba(0, 0, 0, 0.45);
	}

		.audio {
			padding: 12px 0 18px;
			border-bottom: 1px dashed rgba(214, 179, 95, 0.18);
		}

		.audio audio {
			width: 100%;
		}

	.composer {
		grid-column: 2;
		grid-row: 2;
		border-top: 1px solid rgba(214, 179, 95, 0.20);
		padding: 14px 16px;
		background: rgba(12, 10, 16, 0.35);
	}

	.input {
		width: 100%;
		resize: vertical;
		border-radius: 12px;
		padding: 12px 12px;
		border: 1px solid rgba(214, 179, 95, 0.30);
		background: rgba(10, 9, 14, 0.55);
		color: var(--ink);
		outline: none;
		font: inherit;
	}

	.actions {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		margin-top: 10px;
	}
</style>
