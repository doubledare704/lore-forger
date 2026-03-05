<script lang="ts">
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

	interface Props {
		worldState: WorldState | null;
		inventory: InventoryItem[];
	}

	let { worldState, inventory } = $props<Props>();
</script>

<div class="sidebar">
	<div class="sidebar-section">
		<h3>World State</h3>
		{#if worldState}
			{#if worldState.campaign}
				<div class="campaign-info">
					<h4 class="lore">{worldState.campaign.title}</h4>
					<p class="premise">{worldState.campaign.premise}</p>
					<div class="tag-row">
						<span class="tag mono">{worldState.campaign.tone}</span>
					</div>
				</div>
			{/if}

			{#if worldState.locations && worldState.locations.length > 0}
				<div class="subsection">
					<h5>Locations</h5>
					<ul class="clean-list">
						{#each worldState.locations as loc (loc.name)}
							<li>
								<details>
									<summary><strong>{loc.name}</strong></summary>
									<p class="small">{loc.description}</p>
									<div class="tag-row">
										{#each loc.tags as tag (tag)}
											<span class="tag-tiny mono">{tag}</span>
										{/each}
									</div>
								</details>
							</li>
						{/each}
					</ul>
				</div>
			{/if}

			{#if worldState.npcs && worldState.npcs.length > 0}
				<div class="subsection">
					<h5>NPCs</h5>
					<ul class="clean-list">
						{#each worldState.npcs as npc (npc.name)}
							<li>
								<details>
									<summary><strong>{npc.name}</strong> ({npc.role})</summary>
									<p class="small">{npc.description}</p>
									<p class="small"><em>Location: {npc.location}</em></p>
								</details>
							</li>
						{/each}
					</ul>
				</div>
			{/if}

			{#if worldState.quests && worldState.quests.length > 0}
				<div class="subsection">
					<h5>Quests</h5>
					<ul class="clean-list">
						{#each worldState.quests as q (q.name)}
							<li>
								<details>
									<summary><strong>{q.name}</strong> <span class="status {q.status}">{q.status}</span></summary>
									<p class="small">{q.summary}</p>
								</details>
							</li>
						{/each}
					</ul>
				</div>
			{/if}
		{:else}
			<p class="hint">No world state derived yet. Interact with the grimoire to build your world.</p>
		{/if}
	</div>

	<div class="sidebar-section">
		<h3>Inventory</h3>
		{#if inventory.length > 0}
			<ul class="clean-list">
				{#each inventory as item (item.name)}
					<li class="inventory-item">
						<span class="mono-bold">{item.qty}x</span>
						<span>{item.name}</span>
						{#if item.description}
							<div class="small muted">{item.description}</div>
						{/if}
					</li>
				{/each}
			</ul>
		{:else}
			<p class="hint">Your bags are empty.</p>
		{/if}
	</div>
</div>

<style>
	.sidebar {
		height: 100%;
		overflow-y: auto;
		background: rgba(0, 0, 0, 0.25);
		border-right: 1px solid rgba(214, 179, 95, 0.2);
		padding: 16px;
		color: #bcae8a;
		font-family: ui-serif, Georgia, serif;
	}

	h3 {
		color: #d6b35f;
		border-bottom: 1px solid rgba(214, 179, 95, 0.3);
		margin-bottom: 12px;
		font-size: 1.1em;
		text-transform: uppercase;
		letter-spacing: 0.1em;
	}

	h4 {
		margin: 0 0 8px;
	}

	h5 {
		color: #d6b35f;
		margin: 16px 0 8px;
		font-variant: small-caps;
		border-bottom: 1px dashed rgba(214, 179, 95, 0.15);
	}

	.sidebar-section {
		margin-bottom: 24px;
	}

	.premise {
		font-style: italic;
		font-size: 0.9em;
		margin-bottom: 12px;
	}

	.clean-list {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.clean-list li {
		margin-bottom: 8px;
	}

	details summary {
		cursor: pointer;
		outline: none;
		user-select: none;
	}

	.small {
		font-size: 0.85em;
		margin: 4px 0;
	}

	.muted {
		opacity: 0.7;
	}

	.mono {
		font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
		font-size: 0.8em;
	}

	.mono-bold {
		font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
		font-weight: bold;
		color: #d6b35f;
	}

	.tag {
		background: rgba(214, 179, 95, 0.15);
		color: #d6b35f;
		padding: 2px 6px;
		border-radius: 4px;
		border: 1px solid rgba(214, 179, 95, 0.3);
	}

	.tag-tiny {
		font-size: 0.7em;
		background: rgba(214, 179, 95, 0.1);
		padding: 1px 4px;
		border-radius: 3px;
		margin-right: 4px;
	}

	.tag-row {
		margin-top: 4px;
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
	}

	.status {
		font-size: 0.7em;
		text-transform: uppercase;
		padding: 1px 4px;
		border-radius: 3px;
		vertical-align: middle;
	}

	.status.open { border: 1px solid #5fd67c; color: #5fd67c; }
	.status.completed { border: 1px solid #5f92d6; color: #5f92d6; }
	.status.failed { border: 1px solid #d65f5f; color: #d65f5f; }

	.inventory-item {
		padding: 6px 0;
		border-bottom: 1px solid rgba(214, 179, 95, 0.05);
	}

	.hint {
		font-style: italic;
		font-size: 0.85em;
		opacity: 0.6;
	}
</style>
