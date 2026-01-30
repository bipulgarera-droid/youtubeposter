/**
 * YouTube Niche Verifier - Main JavaScript
 * Handles UI interactions and API calls
 */

// Application State
const state = {
    videos: [],
    savedVideos: [],
    selectedVideoIds: [],  // For multi-select
    transcript: null,
    articles: [],
    script: null,
    screenshots: [],
    currentStep: 1,
    projects: [],
    currentProject: null,
    workflowMode: 'manual'  // 'manual' or 'auto'
};

// DOM Elements
const tabs = document.querySelectorAll('.tab');
const steps = document.querySelectorAll('.step');
const loadingOverlay = document.getElementById('loading');
const loadingText = document.getElementById('loading-text');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    loadState();
});

// Tab Navigation
function setupTabs() {
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const stepNum = parseInt(tab.dataset.step);
            switchToStep(stepNum);
        });
    });
}

function switchToStep(stepNum) {
    state.currentStep = stepNum;
    updateStepUI(stepNum);

    tabs.forEach(tab => {
        tab.classList.toggle('active', parseInt(tab.dataset.step) === stepNum);
    });

    steps.forEach(step => {
        step.classList.toggle('active', step.id === `step-${stepNum}`);
    });
}

function markTabComplete(stepNum) {
    const tab = document.querySelector(`.tab[data-step="${stepNum}"]`);
    if (tab) tab.classList.add('completed');
}

// Update UI elements based on current state when switching steps
function updateStepUI(stepNum) {
    if (stepNum === 4) {
        // News Research Step: Update transcript status
        updateNewsDataPreview();
    }
    if (stepNum === 5) {
        // Script Step: Update transcript/articles status AND Reference Video Indicator
        updateScriptDataPreview();

        const indicator = document.getElementById('reference-video-indicator');
        const titleSpan = document.getElementById('reference-video-title');

        if (state.selectedVideoIds.length > 0) {
            // Find the video object
            const video = state.savedVideos.find(v => v.video_id === state.selectedVideoIds[0]);
            if (video) {
                titleSpan.textContent = video.title.substring(0, 50) + (video.title.length > 50 ? '...' : '');
                indicator.style.display = 'block';
            }
        } else {
            indicator.style.display = 'none';
        }
    }
}

// ============== LIVE LOGS ==============

function clearLogs() {
    const logsContainer = document.getElementById('live-logs');
    if (logsContainer) {
        logsContainer.innerHTML = '<div class="log-entry">> System ready...</div>';
    }
}

function addLog(message, type = '') {
    const logsContainer = document.getElementById('live-logs');
    if (logsContainer) {
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        entry.textContent = `> ${message}`;
        logsContainer.appendChild(entry);
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }
    console.log(`[LOG ${type}] ${message}`);  // Also log to console
}

// Loading State with Logs
function showLoading(message = 'Processing...') {
    loadingText.textContent = message;
    clearLogs();
    addLog(message, 'info');
    loadingOverlay.classList.add('active');
}

function hideLoading() {
    addLog('Operation complete.', 'success');
    setTimeout(() => {
        loadingOverlay.classList.remove('active');
    }, 500);  // Short delay so user can see final log
}

// Toast Notifications
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// Format Numbers
function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

// ============== PROJECT MANAGEMENT ==============

function showNewProjectModal() {
    document.getElementById('project-modal').classList.add('active');
    document.getElementById('project-niche').focus();
}

function hideNewProjectModal() {
    document.getElementById('project-modal').classList.remove('active');
    document.getElementById('project-niche').value = '';
}

async function createProject() {
    const niche = document.getElementById('project-niche').value.trim();
    if (!niche) {
        showToast('Please enter a niche', 'error');
        return;
    }

    showLoading('Creating project...');

    try {
        const response = await fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ niche })
        });

        const result = await response.json();

        if (result.success) {
            state.projects.push(result.project);
            state.currentProject = result.project.id;
            updateProjectSelector();
            hideNewProjectModal();
            showToast('Project created!');
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        showToast('Failed to create project', 'error');
    } finally {
        hideLoading();
    }
}

async function selectProject(projectId) {
    if (!projectId) return;

    try {
        const response = await fetch(`/api/projects/${projectId}/select`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            state.currentProject = projectId;
            await loadSavedVideos();
            showToast(`Switched to project: ${result.project.niche}`);
        }
    } catch (error) {
        showToast('Failed to select project', 'error');
    }
}

function updateProjectSelector() {
    const select = document.getElementById('project-select');
    select.innerHTML = '<option value="">Select Project</option>';

    state.projects.forEach(project => {
        const option = document.createElement('option');
        option.value = project.id;
        option.textContent = project.niche;
        if (project.id === state.currentProject) {
            option.selected = true;
        }
        select.appendChild(option);
    });
}

// ============== VIDEO DISCOVERY ==============

// ============== VIDEO DISCOVERY ==============

async function discoverVideos() {
    const query = document.getElementById('query').value;
    const multiplier = parseFloat(document.getElementById('multiplier').value);
    const days = parseInt(document.getElementById('past-days').value);
    const maxResults = parseInt(document.getElementById('max-results').value);
    const minViews = parseInt(document.getElementById('min-views').value) || 0;
    const minDuration = parseFloat(document.getElementById('min-duration').value) || 0;

    if (!query) {
        showToast('Please enter a search query', 'error');
        return;
    }

    showLoading('Searching YouTube...');

    try {
        const response = await fetch('/api/discover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query,
                multiplier,
                days,
                max_results: maxResults,
                min_views: minViews,
                min_duration_minutes: minDuration
            })
        });

        const result = await response.json();

        if (result.success) {
            state.videos = result.videos;
            renderVideosTable(result.videos);
            showToast(result.message);
            if (result.videos.length > 0) markTabComplete(1);
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        console.error('Search error details:', error);
        console.error('Error message:', error.message);
        console.error('Error stack:', error.stack);
        showToast('Failed to search videos: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Render Videos Table (Discovery tab)
let discoverySortOrder = 'desc'; // default: highest multiplier first

function renderVideosTable(videos) {
    const container = document.getElementById('videos-container');

    if (videos.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">😔</span>
                <p>No videos found. Try adjusting the multiplier.</p>
            </div>
        `;
        return;
    }

    // Sort videos by multiplier
    const sortedVideos = [...videos].sort((a, b) => {
        return discoverySortOrder === 'desc'
            ? (b.multiplier || 0) - (a.multiplier || 0)
            : (a.multiplier || 0) - (b.multiplier || 0);
    });

    let html = `
        <div style="margin-bottom: 12px; display: flex; gap: 8px; align-items: center;">
            <span style="font-size: 13px; color: var(--text-muted);">Sort by Multiplier:</span>
            <button class="btn-secondary ${discoverySortOrder === 'desc' ? 'active' : ''}" 
                    onclick="setDiscoverySortOrder('desc')" style="padding: 4px 12px; font-size: 12px;">
                ↓ High to Low
            </button>
            <button class="btn-secondary ${discoverySortOrder === 'asc' ? 'active' : ''}" 
                    onclick="setDiscoverySortOrder('asc')" style="padding: 4px 12px; font-size: 12px;">
                ↑ Low to High
            </button>
        </div>
        <table class="video-table">
            <thead>
                <tr>
                    <th>Thumbnail</th>
                    <th>Title</th>
                    <th>Channel</th>
                    <th>Views</th>
                    <th>Subs</th>
                    <th>Posted</th>
                    <th>Multiplier</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
    `;

    sortedVideos.forEach(video => {
        const multiplierClass = video.multiplier > 5 ? 'very-high' : (video.multiplier > 2 ? 'high' : '');
        const isSaved = (state.savedVideos || []).some(v => v.video_id === video.video_id);
        const postedDate = video.published_at ? formatDate(video.published_at) : '-';

        html += `
            <tr data-video-id="${video.video_id}">
                <td>
                    <img class="video-thumbnail" src="${video.thumbnail_url}" alt="${video.title}">
                </td>
                <td>
                    <a class="video-title-link" href="https://youtube.com/watch?v=${video.video_id}" target="_blank">
                        ${video.title}
                    </a>
                </td>
                <td>
                    <div class="video-channel">${video.channel_name}</div>
                </td>
                <td>${formatNumber(video.view_count)}</td>
                <td>${formatNumber(video.subscriber_count)}</td>
                <td style="font-size: 12px; color: var(--text-muted);">${postedDate}</td>
                <td>
                    <span class="multiplier-badge ${multiplierClass}">${video.multiplier}x</span>
                </td>
                <td>
                    <div class="video-actions">
                        <button class="btn-save ${isSaved ? 'saved' : ''}" onclick="saveVideo('${video.video_id}')" ${isSaved ? 'disabled' : ''}>
                            ${isSaved ? '✓ Saved' : '💾 Save'}
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

function setDiscoverySortOrder(order) {
    discoverySortOrder = order;
    renderVideosTable(state.videos);
}

function formatDate(dateString) {
    if (!dateString) return '-';
    try {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch (e) {
        return dateString.split('T')[0];
    }
}

// ============== SAVED VIDEOS ==============

async function loadSavedVideos() {
    try {
        const response = await fetch('/api/saved-videos');
        const result = await response.json();

        if (result.success) {
            // Store grouped data: { "query1": [...], "query2": [...] }
            state.savedVideoGroups = result.groups || {};
            // Flatten for backward compat with selection logic
            state.savedVideos = Object.values(state.savedVideoGroups).flat();
            renderSavedVideos();
        }
    } catch (error) {
        console.error('Failed to load saved videos:', error);
    }
}

async function saveVideo(videoId) {
    if (!state.currentProject) {
        showToast('Create a project first', 'error');
        return;
    }

    const video = state.videos.find(v => v.video_id === videoId);
    if (!video) return;

    // Get current search query from the discovery search input
    const searchInput = document.getElementById('search-query');
    const searchQuery = searchInput ? searchInput.value.trim() : 'Uncategorized';

    try {
        const response = await fetch('/api/saved-videos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video, search_query: searchQuery })
        });

        const result = await response.json();

        if (result.success) {
            // Add to the grouped state
            if (!state.savedVideoGroups) state.savedVideoGroups = {};
            if (!state.savedVideoGroups[searchQuery]) state.savedVideoGroups[searchQuery] = [];
            state.savedVideoGroups[searchQuery].push(video);
            state.savedVideos = Object.values(state.savedVideoGroups).flat();

            renderVideosTable(state.videos);
            renderSavedVideos();
            showToast(`Saved to "${searchQuery}"!`);
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        showToast('Failed to save video', 'error');
    }
}

async function removeVideo(videoId) {
    try {
        const response = await fetch(`/api/saved-videos/${videoId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            // Update grouped state
            if (state.savedVideoGroups) {
                for (const groupName of Object.keys(state.savedVideoGroups)) {
                    state.savedVideoGroups[groupName] = state.savedVideoGroups[groupName].filter(v => v.video_id !== videoId);
                    // Clean up empty groups
                    if (state.savedVideoGroups[groupName].length === 0) {
                        delete state.savedVideoGroups[groupName];
                    }
                }
            }
            state.savedVideos = state.savedVideos.filter(v => v.video_id !== videoId);
            state.selectedVideoIds = state.selectedVideoIds.filter(id => id !== videoId);
            renderSavedVideos();
            updateSelectedCount();
            showToast('Video removed');
        }
    } catch (error) {
        showToast('Failed to remove video', 'error');
    }
}

let savedSortOrder = 'desc'; // default: highest multiplier first
let savedSortBy = 'multiplier'; // 'multiplier' or 'date'

function renderSavedVideos() {
    const container = document.getElementById('saved-videos-container');
    const groups = state.savedVideoGroups || {};
    const groupNames = Object.keys(groups);

    if (groupNames.length === 0 || state.savedVideos.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">💾</span>
                <p>No saved videos. Save videos from Discovery.</p>
            </div>
        `;
        document.getElementById('workflow-actions').style.display = 'none';
        return;
    }

    // Sort controls (apply to all groups)
    let html = `
        <div style="margin-bottom: 12px; display: flex; gap: 16px; align-items: center; flex-wrap: wrap;">
            <div style="display: flex; gap: 8px; align-items: center;">
                <span style="font-size: 13px; color: var(--text-muted);">Sort by:</span>
                <button class="btn-secondary ${savedSortBy === 'multiplier' ? 'active' : ''}" 
                        onclick="setSavedSortBy('multiplier')" style="padding: 4px 12px; font-size: 12px;">
                    📊 Multiplier
                </button>
                <button class="btn-secondary ${savedSortBy === 'date' ? 'active' : ''}" 
                        onclick="setSavedSortBy('date')" style="padding: 4px 12px; font-size: 12px;">
                    📅 Date
                </button>
            </div>
            <div style="display: flex; gap: 8px; align-items: center;">
                <button class="btn-secondary ${savedSortOrder === 'desc' ? 'active' : ''}" 
                        onclick="setSavedSortOrder('desc')" style="padding: 4px 12px; font-size: 12px;">
                    ↓ ${savedSortBy === 'date' ? 'Recent First' : 'High to Low'}
                </button>
                <button class="btn-secondary ${savedSortOrder === 'asc' ? 'active' : ''}" 
                        onclick="setSavedSortOrder('asc')" style="padding: 4px 12px; font-size: 12px;">
                    ↑ ${savedSortBy === 'date' ? 'Oldest First' : 'Low to High'}
                </button>
            </div>
            <div style="margin-left: auto;">
                <input type="checkbox" id="select-all" onchange="toggleSelectAll(this)">
                <label for="select-all" style="font-size: 13px; cursor: pointer;">Select All</label>
            </div>
        </div>
    `;

    // Render each group as a collapsible box
    groupNames.forEach(groupName => {
        const groupVideos = groups[groupName] || [];
        if (groupVideos.length === 0) return;

        // Sort videos within group
        const sortedVideos = [...groupVideos].sort((a, b) => {
            if (savedSortBy === 'date') {
                const dateA = new Date(a.published_at || 0);
                const dateB = new Date(b.published_at || 0);
                return savedSortOrder === 'desc' ? dateB - dateA : dateA - dateB;
            } else {
                return savedSortOrder === 'desc'
                    ? (b.multiplier || 0) - (a.multiplier || 0)
                    : (a.multiplier || 0) - (b.multiplier || 0);
            }
        });

        html += `
            <div class="saved-group-box" style="border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 16px; overflow: hidden;">
                <div class="saved-group-header" style="background: var(--bg-secondary); padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; cursor: pointer;" onclick="toggleGroupCollapse('${groupName}')">
                    <h3 style="margin: 0; font-size: 15px; font-weight: 600;">
                        🔍 ${groupName} <span style="font-weight: 400; color: var(--text-muted);">(${groupVideos.length} videos)</span>
                    </h3>
                    <span class="collapse-icon" id="collapse-${groupName}">▼</span>
                </div>
                <div class="saved-group-content" id="group-content-${groupName}" style="padding: 0;">
                    <table class="video-table" style="margin: 0;">
                        <thead>
                            <tr>
                                <th style="width: 40px;"></th>
                                <th>Thumbnail</th>
                                <th>Title</th>
                                <th>Channel</th>
                                <th>Subs</th>
                                <th>Posted</th>
                                <th>Multiplier</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
        `;

        sortedVideos.forEach(video => {
            const isSelected = state.selectedVideoIds.includes(video.video_id);
            const multiplierClass = video.multiplier > 5 ? 'very-high' : (video.multiplier > 2 ? 'high' : '');
            const postedDate = video.published_at ? formatDate(video.published_at) : '-';

            html += `
                <tr class="${isSelected ? 'selected' : ''}" data-video-id="${video.video_id}">
                    <td>
                        <input type="checkbox" class="video-checkbox" 
                               ${isSelected ? 'checked' : ''} 
                               onchange="toggleVideoSelection('${video.video_id}', this.checked)">
                    </td>
                    <td>
                        <img class="video-thumbnail" src="${video.thumbnail_url}" alt="${video.title}">
                    </td>
                    <td>
                        <a class="video-title-link" href="https://youtube.com/watch?v=${video.video_id}" target="_blank">
                            ${video.title}
                        </a>
                    </td>
                    <td>
                        <div class="video-channel">${video.channel_name}</div>
                    </td>
                    <td>${formatNumber(video.subscriber_count || 0)}</td>
                    <td style="font-size: 12px; color: var(--text-muted);">${postedDate}</td>
                    <td>
                        <span class="multiplier-badge ${multiplierClass}">${video.multiplier}x</span>
                    </td>
                    <td>
                        <button class="btn-remove" onclick="removeVideo('${video.video_id}')">🗑️ Remove</button>
                    </td>
                </tr>
            `;
        });

        html += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
    document.getElementById('workflow-actions').style.display = 'flex';
    updateSelectedCount();
}

// Toggle collapse/expand for a group
function toggleGroupCollapse(groupName) {
    const content = document.getElementById(`group-content-${groupName}`);
    const icon = document.getElementById(`collapse-${groupName}`);
    if (content.style.display === 'none') {
        content.style.display = 'block';
        icon.textContent = '▼';
    } else {
        content.style.display = 'none';
        icon.textContent = '▶';
    }
}

function setSavedSortOrder(order) {
    savedSortOrder = order;
    renderSavedVideos();
}

function setSavedSortBy(by) {
    savedSortBy = by;
    renderSavedVideos();
}

function toggleSelectAll(checkbox) {
    if (checkbox.checked) {
        state.selectedVideoIds = state.savedVideos.map(v => v.video_id);
    } else {
        state.selectedVideoIds = [];
    }
    renderSavedVideos();
}

function toggleVideoSelection(videoId, isChecked) {
    if (isChecked) {
        if (!state.selectedVideoIds.includes(videoId)) {
            state.selectedVideoIds.push(videoId);
        }
    } else {
        state.selectedVideoIds = state.selectedVideoIds.filter(id => id !== videoId);
    }
    updateSelectedCount();
}

function updateSelectedCount() {
    document.getElementById('selected-count').textContent = state.selectedVideoIds.length;
}

// ============== WORKFLOW MODES ==============

async function runWorkflow(mode) {
    if (state.selectedVideoIds.length === 0) {
        showToast('Select at least one video', 'error');
        return;
    }

    state.workflowMode = mode;

    // Select the videos
    await fetch('/api/select-videos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_ids: state.selectedVideoIds })
    });

    if (mode === 'manual') {
        // Human in Loop - just go to transcription step
        renderSelectedVideosInfo();
        switchToStep(3);
        showToast('Videos selected. Proceed with transcription.');
    } else {
        // Automatic - run full pipeline
        await runAutomaticPipeline();
    }
}

async function runAutomaticPipeline() {
    showLoading('Running automatic pipeline...');

    try {
        // Step 1: Transcribe first selected video
        showLoading('Step 1/4: Transcribing videos...');
        const transcribeResponse = await fetch('/api/transcribe', { method: 'POST' });
        const transcribeResult = await transcribeResponse.json();

        if (!transcribeResult.success) {
            throw new Error(transcribeResult.message);
        }
        state.transcript = transcribeResult.transcript;
        markTabComplete(3);

        // Step 2: Search news
        showLoading('Step 2/4: Searching news articles...');
        const firstVideo = state.savedVideos.find(v => v.video_id === state.selectedVideoIds[0]);
        const newsTopic = firstVideo ? firstVideo.title : 'finance news';

        const newsResponse = await fetch('/api/search-news', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic: newsTopic, num_articles: 20 })
        });
        const newsResult = await newsResponse.json();

        if (!newsResult.success) {
            throw new Error(newsResult.message);
        }
        state.articles = newsResult.articles;
        markTabComplete(4);

        // Step 3: Generate script
        showLoading('Step 3/4: Generating script...');
        const scriptResponse = await fetch('/api/generate-script', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic: newsTopic })
        });
        const scriptResult = await scriptResponse.json();

        if (!scriptResult.success) {
            throw new Error(scriptResult.message);
        }
        state.script = scriptResult.script;
        markTabComplete(5);

        // Step 4: Capture screenshots
        showLoading('Step 4/4: Capturing screenshots...');
        const screenshotResponse = await fetch('/api/capture-screenshots', { method: 'POST' });
        const screenshotResult = await screenshotResponse.json();

        if (screenshotResult.success) {
            state.screenshots = screenshotResult.screenshots || [];
            markTabComplete(6);
        }

        // Render everything
        renderTranscript(state.transcript);
        renderArticlesList(state.articles);
        renderScript(state.script);
        renderScreenshots(state.screenshots);

        showToast('🎉 Pipeline complete!');
        switchToStep(5);  // Go to script tab

    } catch (error) {
        showToast(`Pipeline failed: ${error.message}`, 'error');
    } finally {
        hideLoading();
    }
}

function renderSelectedVideosInfo() {
    const container = document.getElementById('selected-video-info');
    const selected = state.savedVideos.filter(v => state.selectedVideoIds.includes(v.video_id));

    if (selected.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">⬅️</span>
                <p>Select videos from the Saved tab first</p>
            </div>
        `;
        return;
    }

    let html = '';
    selected.forEach(video => {
        html += `
            <div class="selected-video-card" style="margin-bottom: 16px;">
                <img class="selected-video-thumbnail" src="${video.thumbnail_url}" alt="${video.title}">
                <div class="selected-video-info">
                    <h3><a href="https://youtube.com/watch?v=${video.video_id}" target="_blank">${video.title}</a></h3>
                    <p>${video.channel_name} • ${formatNumber(video.view_count)} views • ${video.multiplier}x multiplier</p>
                </div>
            </div>
        `;
    });

    html += `
        <button class="btn-primary" onclick="transcribeVideo()" style="margin-top: 12px;">
            <span class="btn-icon">🎙️</span> Transcribe Videos
        </button>
    `;

    container.innerHTML = html;
}

// ============== TRANSCRIPTION ==============

async function transcribeVideo() {
    showLoading('Downloading and transcribing video...');
    addLog('Starting transcription process...', 'info');

    try {
        addLog('Sending request to /api/transcribe...', '');
        const response = await fetch('/api/transcribe', { method: 'POST' });
        addLog(`Server responded with status: ${response.status}`, '');

        const result = await response.json();
        addLog(`Response received. Success: ${result.success}`, result.success ? 'success' : 'error');

        if (result.success) {
            addLog(`Transcript length: ${result.transcript?.length || 0} characters`, 'success');
            state.transcript = result.transcript;

            // Get the selected videos for display
            const selectedVideos = state.savedVideos.filter(v => state.selectedVideoIds.includes(v.video_id));
            addLog(`Found ${selectedVideos.length} selected videos to display`, '');

            renderTranscriptWithVideos(selectedVideos, result.transcript);
            addLog('Rendered transcript with videos', 'success');

            showToast('Transcription complete!');
            markTabComplete(3);
        } else {
            addLog(`Error: ${result.message}`, 'error');
            showToast(result.message, 'error');
        }
    } catch (error) {
        addLog(`Exception: ${error.message}`, 'error');
        showToast('Transcription failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

async function transcribeManualUrl() {
    const urlInput = document.getElementById('manual-url-input');
    const url = urlInput.value.trim();

    if (!url) {
        showToast('Please enter a YouTube URL', 'error');
        return;
    }

    // Basic validation
    if (!url.includes('youtube.com') && !url.includes('youtu.be')) {
        showToast('Please enter a valid YouTube URL', 'error');
        return;
    }

    showLoading('Transcribing video...');
    addLog(`Transcribing URL: ${url}`, 'info');

    try {
        const response = await fetch('/api/transcribe-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const result = await response.json();

        if (result.success) {
            state.transcript = result.transcript;

            // Display the transcript
            const container = document.getElementById('transcript-container');
            container.innerHTML = `
                <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg); overflow: hidden;">
                    <div style="padding: 16px; border-bottom: 1px solid var(--border-color);">
                        <h4 style="margin-bottom: 4px; display: flex; align-items: center; gap: 8px;">
                            <span>✅</span> Transcription Complete
                        </h4>
                        <p style="color: var(--text-secondary); font-size: 13px;">
                            Video ID: ${result.video_id} • ${result.word_count} words
                        </p>
                    </div>
                    <div style="padding: 16px; max-height: 400px; overflow-y: auto;">
                        <pre style="white-space: pre-wrap; font-family: inherit; margin: 0; font-size: 14px; line-height: 1.6;">${result.transcript}</pre>
                    </div>
                </div>
            `;

            // Clear input
            urlInput.value = '';

            addLog(`Transcription complete: ${result.word_count} words`, 'success');
            showToast('Transcription complete!');
            markTabComplete(3);
        } else {
            addLog(`Error: ${result.message}`, 'error');
            showToast(result.message, 'error');
        }
    } catch (error) {
        addLog(`Exception: ${error.message}`, 'error');
        showToast('Transcription failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

function renderTranscriptWithVideos(videos, transcript) {
    const container = document.getElementById('transcript-container');

    let html = '<div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg); overflow: hidden;">';

    // Show video info header
    videos.forEach(video => {
        html += `
            <div style="padding: 16px; border-bottom: 1px solid var(--border-color); display: flex; gap: 16px; align-items: center;">
                <img src="${video.thumbnail_url}" alt="${video.title}" style="width: 120px; height: 68px; border-radius: 8px; object-fit: cover;">
                <div>
                    <h4 style="margin-bottom: 4px;">
                        <a href="https://youtube.com/watch?v=${video.video_id}" target="_blank" style="color: var(--accent-primary); text-decoration: none;">${video.title}</a>
                    </h4>
                    <p style="color: var(--text-secondary); font-size: 13px;">${video.channel_name} • ${formatNumber(video.view_count)} views • ${video.multiplier}x</p>
                </div>
            </div>
        `;
    });

    // Show transcript
    html += `
        <div style="padding: 20px;">
            <h3 style="margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
                <span>📝</span> Transcript
                <span style="font-size: 12px; color: var(--text-muted); font-weight: normal;">(${transcript.split(' ').length} words)</span>
            </h3>
            <div class="transcript-text" style="max-height: 400px; overflow-y: auto; white-space: pre-wrap; line-height: 1.8; font-size: 14px; color: var(--text-secondary);">
${transcript}
            </div>
        </div>
        
        <div style="padding: 20px; background: var(--bg-secondary); border-top: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
            <p style="color: var(--text-secondary); font-size: 13px;">✅ Transcript saved. Click below to research news.</p>
            <button class="btn-primary" onclick="goToNewsResearch()">
                <span class="btn-icon">📰</span> Research News
            </button>
        </div>
    `;

    html += '</div>';
    container.innerHTML = html;
}

function goToNewsResearch() {
    switchToStep(4);
    updateNewsDataPreview();
}

function updateNewsDataPreview() {
    // Update the transcript info in News Research tab
    const infoEl = document.getElementById('news-transcript-info');
    const btnEl = document.getElementById('btn-search-news');

    if (state.transcript) {
        const wordCount = state.transcript.split(' ').length;
        infoEl.textContent = `✅ ${wordCount} words loaded from video transcript`;
        infoEl.style.color = 'var(--success)';
        btnEl.disabled = false;
    } else {
        infoEl.textContent = '⚠️ No transcript available - go to Transcription tab first';
        infoEl.style.color = 'var(--warning)';
        btnEl.disabled = true;
    }
}

function updateScriptDataPreview() {
    // Update the info in Script Generation tab
    const transcriptInfo = document.getElementById('script-transcript-info');
    const articlesInfo = document.getElementById('script-articles-info');
    const btnEl = document.getElementById('btn-generate-script');

    if (state.transcript) {
        const wordCount = state.transcript.split(' ').length;
        transcriptInfo.textContent = `✅ ${wordCount} words`;
        transcriptInfo.style.color = 'var(--success)';
    } else {
        transcriptInfo.textContent = '❌ Not loaded';
        transcriptInfo.style.color = 'var(--error)';
    }

    if (state.articles && state.articles.length > 0) {
        articlesInfo.textContent = `✅ ${state.articles.length} articles`;
        articlesInfo.style.color = 'var(--success)';
        btnEl.disabled = false;
    } else {
        articlesInfo.textContent = '❌ Not loaded';
        articlesInfo.style.color = 'var(--error)';
        btnEl.disabled = true;
    }
}

function renderTranscript(transcript) {
    const container = document.getElementById('transcript-container');
    container.innerHTML = `
        <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: 20px;">
            <h3 style="margin-bottom: 16px;">📝 Transcript</h3>
            <div class="transcript-text" style="max-height: 300px; overflow-y: auto;">${transcript}</div>
        </div>
    `;
}

// ============== NEWS SEARCH ==============

// Search news by typing a topic directly (no transcript needed)
async function searchNewsByTopic() {
    const topicInput = document.getElementById('news-topic-input');
    const topic = topicInput ? topicInput.value.trim() : '';

    if (!topic) {
        showToast('Please enter a topic to search', 'error');
        return;
    }

    showLoading(`Searching news for: ${topic}...`);
    addLog(`Topic: "${topic}"`, 'info');

    try {
        const daysLimitSelect = document.getElementById('days-limit-select');
        const daysLimit = daysLimitSelect ? parseInt(daysLimitSelect.value) : 3;
        addLog(`Searching news from last ${daysLimit} days...`, 'info');

        const response = await fetch('/api/search-news', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                topic: topic,
                num_articles: 30,
                days_limit: daysLimit
            })
        });

        const result = await response.json();
        addLog(`Response: ${result.message}`, result.success ? 'success' : 'error');

        if (result.success) {
            state.articles = result.articles;
            addLog(`Found ${result.articles.length} articles`, 'success');
            renderArticlesList(result.articles);
            showToast(result.message);
            markTabComplete(4);
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        addLog(`Error: ${error.message}`, 'error');
        showToast('Failed to search news', 'error');
    } finally {
        hideLoading();
    }
}

// Search news from transcript (existing)

async function searchNewsFromTranscript() {
    if (!state.transcript) {
        showToast('No transcript available', 'error');
        return;
    }

    showLoading('Analyzing transcript and searching for news...');
    addLog('Extracting key topics from transcript...', 'info');

    try {
        const daysLimitSelect = document.getElementById('days-limit-select');
        const daysLimit = daysLimitSelect ? parseInt(daysLimitSelect.value) : 7;
        addLog(`Searching news from last ${daysLimit} days...`, 'info');

        const response = await fetch('/api/search-news', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                transcript: state.transcript,
                num_articles: 30,
                days_limit: daysLimit
            })
        });

        const result = await response.json();
        addLog(`Response: ${result.message}`, result.success ? 'success' : 'error');

        if (result.success) {
            state.articles = result.articles;
            addLog(`Found ${result.articles.length} articles`, 'success');
            renderArticlesList(result.articles);
            showToast(result.message);
            markTabComplete(4);
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        addLog(`Error: ${error.message}`, 'error');
        showToast('Failed to search news', 'error');
    } finally {
        hideLoading();
    }
}

async function searchNews() {
    // Legacy function - redirect to new one
    await searchNewsFromTranscript();
}

function renderArticlesList(articles) {
    const container = document.getElementById('articles-container');

    if (articles.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">😔</span>
                <p>No articles found. Try a different topic.</p>
            </div>
        `;
        return;
    }

    let html = '<div class="articles-list">';

    articles.forEach((article, index) => {
        html += `
            <div class="article-item">
                <div class="article-number">${index + 1}</div>
                <div class="article-content">
                    <div class="article-title">
                        <a href="${article.url}" target="_blank">${article.title}</a>
                    </div>
                    <div class="article-snippet">${article.snippet}</div>
                    <div class="article-meta">
                        <span>📰 ${article.source}</span>
                        ${article.date ? `<span>📅 ${article.date}</span>` : ''}
                    </div>
                </div>
            </div>
        `;
    });

    html += `
        </div>
        <div style="padding: 20px; border-top: 1px solid var(--border-color);">
            <button class="btn-primary" onclick="goToScriptGeneration()">
                <span class="btn-icon">➡️</span> Continue to Script Generation
            </button>
        </div>
    `;

    container.innerHTML = html;
}

function goToScriptGeneration() {
    switchToStep(5);
    updateScriptDataPreview();
}

// ============== SCRIPT GENERATION (Auto) ==============

// Suggest video topics based on transcript + research
async function suggestTopics() {
    if (!state.transcript && state.articles?.length === 0) {
        showToast('Need transcript or articles first', 'error');
        return;
    }

    showLoading('Generating topic suggestions...');
    addLog('Asking AI for topic suggestions...', 'info');

    try {
        const channelFocus = document.getElementById('channel-focus-input')?.value || '';

        const response = await fetch('/api/suggest-topics', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                transcript: state.transcript?.substring(0, 5000) || '',
                articles: state.articles?.slice(0, 5) || [],
                channel_focus: channelFocus
            })
        });

        const result = await response.json();

        if (result.success && result.topics?.length > 0) {
            // Show container
            document.getElementById('topic-suggestions-container').style.display = 'block';

            // Render topic buttons
            const listDiv = document.getElementById('topic-suggestions-list');
            listDiv.innerHTML = result.topics.map((topic, i) => `
                <label style="display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: 8px; cursor: pointer;">
                    <input type="radio" name="topic-choice" value="${topic}" style="accent-color: var(--accent-primary);"${i === 0 ? ' checked' : ''}>
                    <span style="font-size: 14px;">${topic}</span>
                </label>
            `).join('');

            // Also set first topic as custom input default
            document.getElementById('custom-topic-input').value = result.topics[0];

            showToast(`${result.topics.length} topics suggested!`);
            addLog(`Topics: ${result.topics.join(' | ')}`, 'success');
        } else {
            showToast(result.error || 'No topics generated', 'error');
        }
    } catch (error) {
        showToast('Failed to suggest topics: ' + error.message, 'error');
    }

    hideLoading();
}

// Get selected topic from UI
function getSelectedTopic() {
    const customInput = document.getElementById('custom-topic-input');
    if (customInput?.value?.trim()) {
        return customInput.value.trim();
    }

    const selectedRadio = document.querySelector('input[name="topic-choice"]:checked');
    return selectedRadio?.value || null;
}


// ============== NARRATIVE ENGINE SCRIPT GENERATION ==============

function updateNarrativePreview() {
    const mode = document.getElementById('narrative-mode')?.value || 'words';
    const input = document.getElementById('narrative-value');
    if (mode === 'words') {
        input.value = 3000;
        input.min = 500;
        input.max = 15000;
        input.step = 500;
    } else {
        input.value = 15;
        input.min = 5;
        input.max = 60;
        input.step = 5;
    }
}

async function generateNarrativeScript() {
    // Get topic - prioritize narrative-specific input, then fall back to others
    let topic = document.getElementById('narrative-topic-input')?.value?.trim();
    if (!topic) {
        topic = document.getElementById('custom-topic-input')?.value?.trim();
    }
    if (!topic) {
        const selectedTopic = getSelectedTopic();
        topic = selectedTopic || '';
    }

    if (!topic) {
        showToast('Please enter a topic for the Narrative Engine', 'error');
        return;
    }

    // Get value and mode
    const mode = document.getElementById('narrative-mode')?.value || 'words';
    const value = parseInt(document.getElementById('narrative-value')?.value) || (mode === 'words' ? 3000 : 15);

    // Calculate target minutes
    let targetMinutes;
    let displayValue;
    if (mode === 'words') {
        targetMinutes = Math.round(value / 150); // ~150 words per minute
        displayValue = `${value} words (~${targetMinutes} min)`;
    } else {
        targetMinutes = value;
        displayValue = `${value} min (~${value * 150} words)`;
    }

    showLoading(`Generating ${displayValue} narrative script...`);
    addLog(`🎬 Narrative Engine: Generating "${topic}" (${displayValue})`, 'info');

    try {
        const response = await fetch('/api/generate-narrative-script', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                topic: topic,
                target_minutes: targetMinutes,
                // Pass frontend state in case backend lost it
                transcript: state.transcript,
                articles: state.articles
            })
        });

        const result = await response.json();

        if (result.success) {
            // Store in state
            state.script = {
                raw_text: result.full_script,
                word_count: result.total_words,
                narrative_beats: result.beats
            };
            state.narrativeBeats = result.beats;

            // Render the beats
            renderNarrativeBeats(result.beats, result.full_script, result);

            addLog(`✅ Generated ${result.total_words} words in ${result.beat_count} beats`, 'success');
            showToast(`Script generated: ${result.estimated_minutes} min, ${result.chunk_count} image chunks`);
            markTabComplete(5);
        } else {
            addLog(`❌ Error: ${result.message}`, 'error');
            showToast(result.message, 'error');
        }
    } catch (error) {
        addLog(`❌ Exception: ${error.message}`, 'error');
        showToast('Narrative generation failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}


function renderNarrativeBeats(beats, fullScript, stats) {
    const container = document.getElementById('script-container');

    if (!beats || beats.length === 0) {
        container.innerHTML = '<div class="empty-state"><span class="empty-icon">📜</span><p>No beats generated</p></div>';
        return;
    }

    let html = `
        <div class="narrative-stats" style="background: linear-gradient(135deg, rgba(139, 92, 246, 0.1), rgba(99, 102, 241, 0.1)); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 12px; padding: 16px; margin-bottom: 20px;">
            <div style="display: flex; gap: 24px; flex-wrap: wrap;">
                <div><strong style="color: #8B5CF6;">Total Words:</strong> ${stats.total_words}</div>
                <div><strong style="color: #8B5CF6;">Duration:</strong> ~${stats.estimated_minutes} min</div>
                <div><strong style="color: #8B5CF6;">Beats:</strong> ${stats.beat_count}</div>
                <div><strong style="color: #8B5CF6;">Image Chunks:</strong> ${stats.chunk_count}</div>
            </div>
        </div>
        
        <div class="narrative-beats" style="display: flex; flex-direction: column; gap: 16px;">
    `;

    beats.forEach((beat, index) => {
        const isOverBudget = beat.word_count > beat.word_target * 1.15;
        const isUnderBudget = beat.word_count < beat.word_target * 0.85;
        const statusColor = isOverBudget ? '#f87171' : (isUnderBudget ? '#fbbf24' : '#4ade80');

        html += `
            <div class="beat-card" style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; overflow: hidden;">
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: rgba(139, 92, 246, 0.1); border-bottom: 1px solid var(--border-color);">
                    <div>
                        <span style="font-weight: 600; color: #8B5CF6;">${index + 1}. ${beat.name}</span>
                        <span style="font-size: 12px; color: ${statusColor}; margin-left: 12px;">
                            ${beat.word_count} / ${beat.word_target} words
                        </span>
                        <span style="font-size: 11px; color: var(--text-muted); margin-left: 8px;">
                            (${beat.chunk_count || 0} chunks)
                        </span>
                    </div>
                    <button onclick="regenerateBeat('${beat.id}')" 
                            style="background: rgba(139, 92, 246, 0.2); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; padding: 4px 10px; color: #8B5CF6; cursor: pointer; font-size: 12px;">
                        🔄 Regenerate
                    </button>
                </div>
                <div style="padding: 16px; font-size: 14px; line-height: 1.6; color: var(--text-primary); max-height: 200px; overflow-y: auto;">
                    ${beat.text.replace(/\n/g, '<br>')}
                </div>
            </div>
        `;
    });

    html += '</div>';

    // Add full script view toggle
    html += `
        <div style="margin-top: 20px;">
            <button onclick="toggleFullScript()" class="btn-secondary" style="width: 100%;">
                📄 Toggle Full Script View
            </button>
            <div id="full-script-view" style="display: none; margin-top: 12px; padding: 16px; background: var(--bg-tertiary); border-radius: 8px; white-space: pre-wrap; font-size: 13px; max-height: 500px; overflow-y: auto;">
                ${fullScript}
            </div>
        </div>
    `;

    container.innerHTML = html;
}


function toggleFullScript() {
    const view = document.getElementById('full-script-view');
    if (view) {
        view.style.display = view.style.display === 'none' ? 'block' : 'none';
    }
}


async function regenerateBeat(beatId) {
    const topic = document.getElementById('custom-topic-input')?.value?.trim() || getSelectedTopic() || '';

    showLoading(`Regenerating ${beatId} beat...`);

    try {
        const response = await fetch('/api/regenerate-beat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ beat_id: beatId, topic: topic })
        });

        const result = await response.json();

        if (result.success) {
            // Update state
            if (state.narrativeBeats) {
                for (let i = 0; i < state.narrativeBeats.length; i++) {
                    if (state.narrativeBeats[i].id === beatId) {
                        state.narrativeBeats[i] = result.beat;
                        break;
                    }
                }

                // Recalculate stats
                const totalWords = state.narrativeBeats.reduce((sum, b) => sum + (b.word_count || 0), 0);
                const totalChunks = state.narrativeBeats.reduce((sum, b) => sum + (b.chunk_count || 0), 0);
                const fullScript = state.narrativeBeats.map(b => b.text).join('\n\n');

                state.script = {
                    raw_text: fullScript,
                    word_count: totalWords,
                    narrative_beats: state.narrativeBeats
                };

                // Re-render
                renderNarrativeBeats(state.narrativeBeats, fullScript, {
                    total_words: totalWords,
                    estimated_minutes: (totalWords / 150).toFixed(1),
                    beat_count: state.narrativeBeats.length,
                    chunk_count: totalChunks
                });
            }

            showToast(`${beatId} beat regenerated!`);
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        showToast('Regeneration failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}


// ============== ORIGINAL SCRIPT GENERATION ==============

async function generateScriptAuto() {
    // Get Script Mode first to determine validation rules
    const scriptModeSelect = document.getElementById('script-mode-select');
    const scriptMode = scriptModeSelect ? scriptModeSelect.value : 'original';

    // Validation: Transcript required ONLY for transcript_refined mode
    if (scriptMode === 'transcript_refined' && !state.transcript) {
        showToast('No transcript available. Required for Transcript Refined mode.', 'error');
        return;
    }

    if (!state.articles || state.articles.length === 0) {
        showToast('No articles available - search for news first', 'error');
        return;
    }

    // Get selected topic (if any)
    const selectedTopic = getSelectedTopic();

    showLoading('Generating script with AI...');
    addLog('Starting script generation...', 'info');
    addLog(`Script Mode: ${scriptMode}`, 'info');
    if (selectedTopic) {
        addLog(`Selected Topic: ${selectedTopic}`, 'success');
    }

    addLog(`Using ${state.articles.length} articles as sources`, '');

    // Get selected word count
    const wordCountSelect = document.getElementById('word-count-select');
    const targetWordCount = wordCountSelect ? parseInt(wordCountSelect.value) : 4000;
    addLog(`Target word count: ${targetWordCount.toLocaleString()} words`, '');

    // Get channel focus (optional)
    const channelFocusInput = document.getElementById('channel-focus-input');
    const channelFocus = channelFocusInput ? channelFocusInput.value.trim() : '';
    if (channelFocus) {
        addLog(`Channel focus: ${channelFocus}`, '');
    }

    // Get Reference Video ID (if any)
    const referenceVideoId = state.selectedVideoIds.length > 0 ? state.selectedVideoIds[0] : null;

    try {
        addLog('Fetching article content & sending to Gemini...', '');
        const response = await fetch('/api/generate-script', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                transcript: state.transcript, // Can be null now
                articles: state.articles,
                word_count: targetWordCount,
                channel_focus: channelFocus,
                script_mode: scriptMode,
                selected_topic: selectedTopic,
                reference_video_id: referenceVideoId
            })
        });

        const result = await response.json();
        addLog(`Response: ${result.message}`, result.success ? 'success' : 'error');

        if (result.success) {
            state.script = result.script;
            addLog(`Script generated: ${result.script?.total_words || 'N/A'} words`, 'success');
            renderScript(result.script);
            showToast('Script generated!');
            markTabComplete(5);
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        addLog(`Error: ${error.message}`, 'error');
        showToast('Script generation failed', 'error');
    } finally {
        hideLoading();
    }
}

async function generateScript() {
    // Legacy function - redirect to auto version
    await generateScriptAuto();
}

function renderScript(script) {
    const container = document.getElementById('script-container');

    console.log('Rendering script:', script);

    // Handle null/undefined script
    if (!script) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">❌</span>
                <p>Script data is empty</p>
            </div>
        `;
        return;
    }

    // If script is a string (raw text), display it directly
    if (typeof script === 'string') {
        container.innerHTML = `
            <div style="padding: 20px;">
                <h3 style="margin-bottom: 16px;">📜 Generated Script</h3>
                <div class="script-text" style="white-space: pre-wrap;">${script}</div>
            </div>
        `;
        return;
    }

    let html = `
        <div style="padding: 20px; border-bottom: 1px solid var(--border-color);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div>
                    <h3 style="margin-bottom: 8px;">${script.title || 'Generated Script'}</h3>
                    <p style="color: var(--text-secondary);">Total words: ${script.total_words || 'N/A'} ${script.target_words ? `(target: ${script.target_words})` : ''}</p>
                </div>
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                <button class="btn-secondary" onclick="copyScriptWithLinks()">
                    <span class="btn-icon">📋</span> Copy with Links
                </button>
                <button class="btn-secondary" onclick="copyScriptWithoutLinks()">
                    <span class="btn-icon">🎙️</span> Copy for TTS
                </button>
                <button class="btn-primary" onclick="saveProgress()">
                    <span class="btn-icon">💾</span> Save Progress
                </button>
                <button class="btn-secondary" onclick="editScript()">
                    <span class="btn-icon">✏️</span> Edit Script
                </button>
            </div>
        </div>
    `;

    // Use clean_text (without section markers) for display, fallback to raw_text
    const displayText = script.clean_text || script.raw_text;
    if (displayText) {
        const formattedScript = formatScriptWithLinks(displayText);
        html += `
            <div class="script-content" style="padding: 20px;">
                <div class="script-text" id="script-display" style="white-space: pre-wrap; line-height: 1.8;">
                    ${formattedScript}
                </div>
            </div>
        `;
    } else if (script.hook) {
        html += `
            <div class="script-section">
                <div class="script-section-header">
                    <span class="script-section-title">🎯 Hook</span>
                </div>
                <div class="script-section-content">
                    <p class="script-text">${script.hook}</p>
                </div>
            </div>
        `;
    }

    // Render sections if available (fallback for old format)
    if (!script.raw_text && script.sections) {
        script.sections.forEach((section, index) => {
            html += `
                <div class="script-section">
                    <div class="script-section-header">
                        <span class="script-section-title">${section.heading || `Section ${index + 1}`}</span>
                        <span class="script-section-meta">${section.duration_estimate || ''}</span>
                    </div>
                    <div class="script-section-content">
                        <p class="script-text">${section.content}</p>
                        ${section.visual_note ? `<p style="color: var(--info); font-size: 13px;">📹 ${section.visual_note}</p>` : ''}
                        ${section.sources?.length > 0 ? renderSources(section.sources) : ''}
                    </div>
                </div>
            `;
        });
    }

    html += `
        <div style="padding: 20px; border-top: 1px solid var(--border-color);">
            <button class="btn-primary" onclick="switchToStep(6)">
                <span class="btn-icon">➡️</span> Continue to Screenshots
            </button>
        </div>
    `;

    container.innerHTML = html;
}

// Format script text with highlighted SOURCE links
function formatScriptWithLinks(text) {
    // Split into lines and process
    const lines = text.split('\n');
    let formatted = '';

    lines.forEach(line => {
        const trimmed = line.trim();

        // Check if line is a URL
        if (trimmed.match(/^https?:\/\//)) {
            // Style as a visual source link
            formatted += `<div class="source-link" style="margin: 4px 0; padding: 6px 12px; background: rgba(76, 175, 80, 0.1); border-left: 3px solid var(--success); border-radius: 0 6px 6px 0;"><a href="${trimmed}" target="_blank" style="color: var(--success); word-break: break-all; font-size: 13px;">📸 ${trimmed}</a></div>`;
        } else if (trimmed.length > 0) {
            // Regular paragraph text
            formatted += `<p style="margin: 12px 0; line-height: 1.7;">${trimmed}</p>`;
        } else {
            // Empty line - add spacing
            formatted += '<div style="height: 16px;"></div>';
        }
    });

    return formatted;
}

// Copy script WITH links
function copyScriptWithLinks() {
    if (state.script?.raw_text) {
        navigator.clipboard.writeText(state.script.raw_text);
        showToast('Script with links copied!');
    } else {
        showToast('No script to copy', 'error');
    }
}

// Copy script WITHOUT links (for TTS)
function copyScriptWithoutLinks() {
    if (state.script?.raw_text) {
        // Remove URL lines
        const textOnly = state.script.raw_text
            .split('\n')
            .filter(line => !line.trim().match(/^https?:\/\//))
            .join('\n')
            .replace(/\n{3,}/g, '\n\n'); // Clean up extra blank lines
        navigator.clipboard.writeText(textOnly);
        showToast('Script without links copied (TTS ready)!');
    } else {
        showToast('No script to copy', 'error');
    }
}

// Edit script in modal
function editScript() {
    const displayContainer = document.getElementById('script-display');
    if (!displayContainer || !state.script) {
        showToast('No script to edit', 'error');
        return;
    }

    // Get the clean text for editing
    const editText = state.script.clean_text || state.script.raw_text || '';

    // Replace display with textarea
    const parent = displayContainer.parentElement;
    parent.innerHTML = `
        <textarea id="script-edit-area" style="width: 100%; height: 600px; padding: 15px; background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: 8px; color: var(--text-primary); font-family: inherit; font-size: 14px; line-height: 1.8; resize: vertical;">${editText}</textarea>
        <div style="margin-top: 12px; display: flex; gap: 10px;">
            <button class="btn-primary" onclick="saveScriptEdit()">
                <span class="btn-icon">💾</span> Save Changes
            </button>
            <button class="btn-secondary" onclick="cancelScriptEdit()">
                <span class="btn-icon">❌</span> Cancel
            </button>
        </div>
    `;

    showToast('Edit mode enabled. Make your changes and click Save.');
}

// Save edited script
function saveScriptEdit() {
    const textarea = document.getElementById('script-edit-area');
    if (!textarea) {
        showToast('No edit in progress', 'error');
        return;
    }

    const newText = textarea.value.trim();
    if (!newText) {
        showToast('Script cannot be empty', 'error');
        return;
    }

    // Update state
    state.script.clean_text = newText;
    state.script.raw_text = newText;  // Also update raw_text for chunking
    state.script.total_words = newText.split(/\s+/).length;

    // Re-render the script display
    renderScript(state.script);
    showToast('Script saved successfully!');
}

// Cancel script edit
function cancelScriptEdit() {
    renderScript(state.script);
    showToast('Edit cancelled');
}

// Download script as SRT file
function downloadSRT() {
    if (!state.script?.raw_text) {
        showToast('No script to download', 'error');
        return;
    }

    // Get script text and split into chunks
    const rawText = state.script.raw_text
        .split('\n')
        .filter(line => !line.trim().match(/^https?:\/\//))
        .join('\n');

    // Split by paragraphs (double newline) or by sentences
    const paragraphs = rawText.split(/\n\n+/).filter(p => p.trim());

    let srtContent = '';
    let currentTime = 0;
    const wordsPerSecond = 2.5; // Average speaking rate

    paragraphs.forEach((paragraph, index) => {
        const words = paragraph.trim().split(/\s+/).length;
        const duration = Math.max(2, Math.ceil(words / wordsPerSecond));

        const startTime = formatSRTTime(currentTime);
        const endTime = formatSRTTime(currentTime + duration);

        srtContent += `${index + 1}\n`;
        srtContent += `${startTime} --> ${endTime}\n`;
        srtContent += `${paragraph.trim()}\n\n`;

        currentTime += duration;
    });

    // Download the file
    const blob = new Blob([srtContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'script.srt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast('SRT file downloaded!');
}

// Helper: Format seconds to SRT time format (HH:MM:SS,mmm)
function formatSRTTime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);

    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
}

// Save progress to localStorage
function saveProgress() {
    const saveData = {
        transcript: state.transcript,
        articles: state.articles,
        script: state.script,
        screenshots: state.screenshots,
        claimScreenshots: state.claimScreenshots,
        savedAt: new Date().toISOString()
    };

    // Debug: Log what we're saving
    console.log('💾 SAVING PROGRESS:', {
        hasTranscript: !!saveData.transcript,
        articlesCount: saveData.articles?.length || 0,
        hasScript: !!saveData.script,
        scriptWords: saveData.script?.total_words || 0,
        screenshotsCount: saveData.screenshots?.length || 0,
        claimScreenshotsCount: saveData.claimScreenshots?.length || 0
    });

    try {
        const jsonStr = JSON.stringify(saveData);
        localStorage.setItem('youtube_niche_progress', jsonStr);

        // Verify it was saved
        const verification = localStorage.getItem('youtube_niche_progress');
        if (verification) {
            const savedSize = (jsonStr.length / 1024).toFixed(1);
            showToast(`✅ Saved! (${savedSize} KB) - Script: ${saveData.script?.total_words || 0} words`);
            addLog(`Progress saved: ${savedSize} KB`, 'success');
        } else {
            showToast('⚠️ Save may have failed - localStorage returned null', 'error');
        }
    } catch (e) {
        console.error('Save failed:', e);
        showToast(`❌ Save failed: ${e.message}`, 'error');
    }
}

// Load progress from localStorage
function loadProgress() {
    const saved = localStorage.getItem('youtube_niche_progress');
    console.log('📂 LOADING: Found in localStorage:', saved ? `${(saved.length / 1024).toFixed(1)} KB` : 'NOTHING');

    if (saved) {
        try {
            const data = JSON.parse(saved);

            // Debug: Log what we found
            console.log('📂 LOADED DATA:', {
                hasTranscript: !!data.transcript,
                articlesCount: data.articles?.length || 0,
                hasScript: !!data.script,
                scriptWords: data.script?.total_words || 0,
                screenshotsCount: data.screenshots?.length || 0,
                savedAt: data.savedAt
            });

            if (data.transcript) {
                state.transcript = data.transcript;
                const transcriptInfo = document.getElementById('transcript-info');
                const scriptTranscriptInfo = document.getElementById('script-transcript-info');
                if (transcriptInfo) transcriptInfo.textContent = `${data.transcript.split(' ').length} words`;
                if (scriptTranscriptInfo) scriptTranscriptInfo.textContent = `${data.transcript.split(' ').length} words`;
                markTabComplete(2);
            }
            if (data.articles) {
                state.articles = data.articles;
                renderArticlesList(data.articles);
                const articlesInfo = document.getElementById('script-articles-info');
                if (articlesInfo) articlesInfo.textContent = `${data.articles.length} articles`;
                markTabComplete(4);
            }
            if (data.script) {
                state.script = data.script;
                renderScript(data.script);
                markTabComplete(5);
            }
            if (data.screenshots) {
                state.screenshots = data.screenshots;
                renderScreenshots(data.screenshots);
                markTabComplete(6);
            }
            if (data.claimScreenshots && data.claimScreenshots.length > 0) {
                state.claimScreenshots = data.claimScreenshots;
                renderClaimScreenshots(data.claimScreenshots);
                markTabComplete(6);
            }
            showToast(`Progress loaded (saved ${new Date(data.savedAt).toLocaleString()})`);
            addLog('Progress restored from browser storage', 'success');
        } catch (e) {
            console.error(e);
            showToast('Failed to load saved progress', 'error');
        }
    } else {
        showToast('No saved progress found', 'error');
    }
}

function renderSources(sources) {
    let html = `
        <div class="script-sources">
            <div class="script-sources-title">📚 Sources</div>
    `;

    sources.forEach(source => {
        html += `
            <div class="source-item">
                <a class="source-url" href="${source.url}" target="_blank">${source.title || source.url}</a>
                ${source.highlight_text ? `<p class="source-highlight">"${source.highlight_text}"</p>` : ''}
            </div>
        `;
    });

    html += '</div>';
    return html;
}

// ============== SCREENSHOTS ==============

async function captureScreenshots() {
    if (!state.script) {
        showToast('Generate a script first', 'error');
        return;
    }

    showLoading('Capturing screenshots...');

    try {
        const response = await fetch('/api/capture-screenshots', { method: 'POST' });
        const result = await response.json();

        if (result.success) {
            state.screenshots = result.screenshots || [];
            renderScreenshots(state.screenshots);
            showToast(result.message);
            markTabComplete(6);
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        showToast('Screenshot capture failed', 'error');
    } finally {
        hideLoading();
    }
}

// ============== AI IMAGE GENERATION ==============

async function generateAIImages() {
    if (!state.script) {
        showToast('Generate a script first', 'error');
        return;
    }

    showLoading('Generating AI images... This may take a few minutes.');
    addLog('Starting AI image generation with Gemini 2.5 Flash Image...', 'info');

    try {
        const response = await fetch('/api/generate-ai-images', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ script: state.script.raw_text })
        });

        const result = await response.json();

        if (result.success) {
            addLog(`Generated ${result.generated} of ${result.total} images`, 'success');

            // Store chunks in state
            state.aiImageChunks = result.chunks;

            // Render the images
            renderAIImages(result.chunks);

            showToast(`Generated ${result.generated} AI images!`);
            markTabComplete(6);
        } else {
            addLog(`Error: ${result.message}`, 'error');
            showToast(result.message, 'error');
        }
    } catch (error) {
        addLog(`Exception: ${error.message}`, 'error');
        showToast('AI image generation failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

function renderAIImages(chunks) {
    const container = document.getElementById('screenshots-container');

    if (!chunks || chunks.length === 0) {
        container.innerHTML = '<div class="empty-state"><span class="empty-icon">🖼️</span><p>No images generated</p></div>';
        return;
    }

    let html = '<div class="ai-images-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px;">';

    chunks.forEach((chunk, index) => {
        html += `
            <div class="ai-image-card" style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; overflow: hidden;">
                <div style="position: relative;">
                    <img src="${chunk.image_url}" alt="Chunk ${index + 1}" 
                         style="width: 100%; aspect-ratio: 16/9; object-fit: cover;">
                    <button onclick="regenerateChunkImage(${index}, '${encodeURIComponent(chunk.text)}')" 
                            style="position: absolute; top: 8px; right: 8px; background: rgba(0,0,0,0.7); border: none; border-radius: 8px; padding: 6px 12px; color: white; cursor: pointer; font-size: 12px;">
                        🔄 Regenerate
                    </button>
                </div>
                <div style="padding: 12px;">
                    <p style="font-size: 13px; color: var(--text-primary); margin-bottom: 8px; line-height: 1.4;">${chunk.text}</p>
                    <p style="font-size: 11px; color: var(--text-secondary); font-style: italic;">💡 ${chunk.metaphor || 'AI Generated'}</p>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

async function regenerateChunkImage(index, encodedText) {
    const text = decodeURIComponent(encodedText);

    showLoading(`Regenerating image for chunk ${index + 1}...`);

    try {
        const response = await fetch('/api/regenerate-chunk-image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, index })
        });

        const result = await response.json();

        if (result.success) {
            // Update the chunk in state
            if (state.aiImageChunks && state.aiImageChunks[index]) {
                state.aiImageChunks[index].image_url = result.image_url;
                state.aiImageChunks[index].metaphor = result.metaphor;
            }

            // Re-render
            renderAIImages(state.aiImageChunks);

            showToast('Image regenerated!');
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        showToast('Regeneration failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// ============== CLAIM-BASED SCREENSHOTS ==============

async function captureClaimScreenshots() {
    if (!state.script) {
        showToast('Generate a script first', 'error');
        return;
    }

    showLoading('Generating claim-based screenshots... This may take 15-30 minutes for a full script.');
    addLog('Starting claim-based screenshot generation...', 'info');

    try {
        const response = await fetch('/api/claim-screenshots', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ script: state.script.raw_text })
        });
        const result = await response.json();

        if (result.success) {
            state.claimScreenshots = result.screenshots || [];
            renderClaimScreenshots(result.screenshots);
            addLog(`${result.successful} of ${result.total_chunks} screenshots captured`, 'success');
            showToast(result.message);
            markTabComplete(6);
        } else {
            addLog(result.message, 'error');
            showToast(result.message, 'error');
        }
    } catch (error) {
        addLog(`Error: ${error.message}`, 'error');
        showToast('Claim screenshot capture failed', 'error');
    } finally {
        hideLoading();
    }
}

async function forceLoadAIImages() {
    if (!confirm('Load images from the most recent AI batch? This will replace current chunks.')) return;

    showLoading('Scanning for recent AI images...');

    // Get current script text if available
    let scriptText = null;
    if (state.script && state.script.raw_text) {
        scriptText = state.script.raw_text;
    }

    try {
        const response = await fetch('/api/force-load-ai-images', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ script_text: scriptText })
        });
        const result = await response.json();

        if (result.success) {
            showToast(`✅ Found ${result.count} images`, 'success');
            await loadVideoChunks();
        } else {
            showToast(result.message || 'No images found', 'error');
            showLoading(false);
        }
    } catch (error) {
        console.error(error);
        showToast('Error loading images', 'error');
        showLoading(false);
    }
}

function downloadScreenshots() {
    window.location.href = '/api/download-screenshots';
    showToast('Downloading screenshots...');
}

function renderClaimScreenshots(screenshots) {
    const container = document.getElementById('screenshots-container');

    if (!screenshots || screenshots.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📸</span>
                <p>No claim screenshots captured.</p>
            </div>
        `;
        return;
    }

    let html = `
        <div style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; background: var(--bg-secondary); padding: 15px 0; z-index: 10; border-bottom: 1px solid var(--border-color);">
            <div>
                <h3>Claim-Based Screenshots</h3>
                <p style="color: var(--text-secondary); font-size: 13px;">Each 15-second segment has a matching source screenshot</p>
            </div>
            <div style="display: flex; gap: 10px;">
                <button class="btn-secondary" onclick="downloadScreenshots()">📦 Download All</button>
                <button class="btn-secondary" onclick="copyEditorBrief()">📝 Copy Editor's Brief</button>
            </div>
        </div>
        <div class="screenshots-grid" style="display: flex; flex-direction: column; gap: 20px;">
    `;

    const successful = screenshots.filter(s => s.success).length;
    const failed = screenshots.filter(s => !s.success).length;

    html += `
        <div style="background: var(--bg-tertiary); padding: 15px; border-radius: var(--radius-md); margin-bottom: 10px;">
            <p><strong>📊 Summary:</strong> ${successful} successful, ${failed} failed</p>
        </div>
    `;

    screenshots.forEach((item, index) => {
        const durationSec = Math.round((item.chunk_text?.split(' ').length || 0) / 2.5);
        const audioPath = state.audioFiles?.[index];
        const hasAudio = !!audioPath;

        html += `
            <div class="screenshot-section" style="background: var(--bg-card); padding: 20px; border-radius: var(--radius-lg); border: 1px solid var(--border-color);" id="section-${index}">
                <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 600; color: var(--accent);">SECTION ${index + 1} • ~${durationSec} SEC</span>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <button class="btn-secondary" style="padding: 4px 10px; font-size: 11px;" 
                                onclick="editSectionScript(${index})" title="Edit Script">
                            ✏️ Edit
                        </button>
                        <button class="btn-secondary" style="padding: 4px 10px; font-size: 11px;" 
                                onclick="generateSectionAudio(${index}, this)" 
                                data-text="${encodeURIComponent(item.chunk_text || '')}"
                                id="audio-btn-${index}">
                            ${hasAudio ? '🔄 Regenerate' : '🎙️ Create'} Audio
                        </button>
                        ${item.success ? '✅' : '❌'}
                    </div>
                </div>
                <p style="margin-bottom: 15px; line-height: 1.6;" id="chunk-text-${index}">${item.chunk_text || ''}</p>
                
                <!-- Audio Player (if audio exists) -->
                <div id="audio-container-${index}" style="margin-bottom: 10px; ${hasAudio ? '' : 'display: none;'}">
                    ${hasAudio ? `
                        <audio controls style="width: 100%; height: 40px;">
                            <source src="${audioPath}" type="audio/mpeg">
                        </audio>
                    ` : ''}
                </div>
                
                <!-- Audio Generation Log -->
                <div id="audio-log-${index}" style="display: none; background: var(--bg-tertiary); padding: 10px; border-radius: 6px; font-size: 11px; color: var(--text-secondary); margin-bottom: 10px; max-height: 100px; overflow-y: auto;"></div>
                
                <p style="color: var(--text-secondary); font-size: 12px; margin-bottom: 10px;">🔍 Claim: ${item.claim || ''}</p>
        `;

        if (item.success && item.filename) {
            html += `
                <div style="margin-top: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <a href="${item.url || '#'}" target="_blank" style="color: var(--accent); text-decoration: underline; font-size: 12px; max-width: 70%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">🔗 ${item.url || ''}</a>
                        <a href="/api/screenshots/${item.filename}" download="${item.filename}" class="btn-secondary" style="padding: 4px 10px; font-size: 11px;">📥 Download</a>
                    </div>
                    <img src="/api/screenshots/${item.filename}" 
                         alt="Screenshot ${index + 1}" 
                         style="max-width: 100%; border-radius: var(--radius-md); border: 1px solid var(--border-color);"
                         loading="lazy">
                </div>
            `;
        } else {
            html += `<p style="color: var(--error);">❌ Screenshot Failed: ${item.error || 'Unknown error'}</p>`;
        }

        html += `</div>`;
    });

    html += '</div>';
    container.innerHTML = html;
}

function renderScreenshots(screenshots) {
    const container = document.getElementById('screenshots-container');

    if (screenshots.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📸</span>
                <p>No screenshots captured.</p>
            </div>
        `;
        return;
    }

    // Create the Editor Brief content first (so we can check matches)
    let html = `
        <div style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; background: var(--bg-secondary); padding: 15px 0; z-index: 10; border-bottom: 1px solid var(--border-color);">
            <div>
                <h3>Visual Script & Assets</h3>
                <p style="color: var(--text-secondary); font-size: 13px;">Script text mapped to sources and captured screenshots</p>
            </div>
            <button class="btn-primary" onclick="copyEditorBrief()">
                <span class="btn-icon">📝</span> Copy Editor's Brief
            </button>
        </div >
                <div class="script-visual-view" style="max-width: 800px; margin: 0 auto; padding-bottom: 50px;">
                    `;

    if (state.script && state.script.raw_text) {
        // Parse script and inject screenshots inline
        const chunks = state.script.raw_text.split(/\n\n+/);

        chunks.forEach((chunk, index) => {
            const lines = chunk.trim().split('\n');
            let chunkHtml = `<div class="script-section" style="background: var(--bg-tertiary); padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid var(--border-color);">`;

            // Add section header
            const textContent = lines.filter(l => !l.trim().match(/^https?:\/\//)).join(' ');
            const duration = Math.round(textContent.split(/\s+/).length / 2.5);
            chunkHtml += `<div style="margin-bottom: 10px; font-size: 11px; text-transform: uppercase; color: var(--accent-color); font-weight: bold; letter-spacing: 1px;">Section ${index + 1} • ~${duration} sec</div>`;

            lines.forEach(line => {
                const trimmed = line.trim();
                if (trimmed.match(/^https?:\/\//)) {
                    // It's a URL - Find the screenshot
                    const url = trimmed;
                    const screenshot = screenshots.find(s => s.success && s.url === url);

                    chunkHtml += `
                        <div style="margin-top: 15px; padding: 10px; background: rgba(0,0,0,0.2); border-radius: 6px; border-left: 3px solid var(--accent-color);">
                            <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; display: flex; align-items: center; gap: 6px;">
                                <span>🔗 SOURCE:</span> <a href="${url}" target="_blank" style="color: var(--accent-color); text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${url}</a>
                            </div>
                            `;

                    if (screenshot) {
                        chunkHtml += `
                            <div style="border: 1px solid var(--border-color); border-radius: 4px; overflow: hidden;">
                                <div style="background: #000; padding: 4px 8px; font-size: 10px; font-family: monospace; color: #0f0; border-bottom: 1px solid #333;">
                                    PATH: ${screenshot.screenshot_path}
                                </div>
                                <img src="/api/screenshots/${screenshot.screenshot_path.split('/').pop()}" 
                                     style="width: 100%; height: auto; display: block;" 
                                     alt="Screenshot of ${url}"
                                     onerror="this.style.display='none'; this.nextElementSibling.style.display='block'">
                                <div style="display: none; padding: 20px; text-align: center; color: var(--text-secondary);">Image failed to load</div>
                            </div>
                        `;
                    } else {
                        // Check for failed attempt
                        const failed = screenshots.find(s => !s.success && s.url === url);
                        if (failed) {
                            chunkHtml += `<div style="color: #ff4444; font-size: 13px; font-weight: bold;">❌ Screenshot Failed: ${failed.error || 'Unknown error'}</div>`;
                        } else {
                            chunkHtml += `<div style="color: var(--text-secondary); font-size: 13px; font-style: italic;">⚠️ No screenshot captured for this URL</div>`;
                        }
                    }
                    chunkHtml += `</div>`;
                } else {
                    // It's text
                    chunkHtml += `<p style="line-height: 1.6; margin-bottom: 8px; font-size: 15px;">${line}</p>`;
                }
            });

            chunkHtml += `</div>`;
            html += chunkHtml;
        });
    } else {
        html += `<div style="padding: 20px; text-align: center;">Script not available to map screenshots.</div>`;
    }

    html += '</div>';
    container.innerHTML = html;
}

// ============== RESET ==============

async function resetApp() {
    if (!confirm('Reset all progress?')) return;

    try {
        await fetch('/api/reset', { method: 'POST' });

        state.videos = [];
        state.savedVideos = [];
        state.selectedVideoIds = [];
        state.transcript = null;
        state.articles = [];
        state.script = null;
        state.screenshots = [];

        tabs.forEach(tab => tab.classList.remove('completed'));
        switchToStep(1);

        document.getElementById('videos-container').innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📹</span>
                <p>Enter search criteria and click "Search Videos"</p>
            </div>
        `;

        renderSavedVideos();

        showToast('Application reset');
    } catch (error) {
        showToast('Reset failed', 'error');
    }
}

// ============== AUDIO GENERATION ==============

async function generateSectionAudio(sectionIndex, buttonEl) {
    // Get text from the chunk-text element (in case it was edited)
    const chunkTextEl = document.getElementById(`chunk-text-${sectionIndex}`);
    const text = chunkTextEl ? chunkTextEl.textContent : decodeURIComponent(buttonEl.dataset.text);

    if (!text || text.trim().length === 0) {
        showToast('No text available for this section', 'error');
        return;
    }

    // Show log container
    const logEl = document.getElementById(`audio-log-${sectionIndex}`);
    if (logEl) {
        logEl.style.display = 'block';
        logEl.innerHTML = `<p>🎙️ Starting audio generation...</p>`;
    }

    // Update button to show loading state
    const originalText = buttonEl.innerHTML;
    buttonEl.innerHTML = '⏳ Generating...';
    buttonEl.disabled = true;

    const logMessage = (msg) => {
        if (logEl) {
            logEl.innerHTML += `<p>${msg}</p>`;
            logEl.scrollTop = logEl.scrollHeight;
        }
    };

    try {
        logMessage(`📝 Text: ${text.substring(0, 50)}...`);
        logMessage(`🔄 Sending to ElevenLabs API...`);

        const response = await fetch('/api/generate-audio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: text,
                section_index: sectionIndex
            })
        });

        const result = await response.json();

        if (result.success) {
            logMessage(`✅ Audio generated! Duration: ~${Math.round(result.duration_estimate)}s`);
            logMessage(`📁 File: ${result.filename}`);

            // Update audio player
            const audioContainer = document.getElementById(`audio-container-${sectionIndex}`);
            if (audioContainer) {
                audioContainer.style.display = 'block';
                audioContainer.innerHTML = `
                    <audio controls style="width: 100%; height: 40px;">
                        <source src="${result.path}?t=${Date.now()}" type="audio/mpeg">
                    </audio>
                `;
            }

            // Store audio path in state
            if (!state.audioFiles) state.audioFiles = {};
            state.audioFiles[sectionIndex] = result.path;

            showToast(`Audio created for Section ${sectionIndex + 1} (~${Math.round(result.duration_estimate)}s)`);
            buttonEl.innerHTML = '🔄 Regenerate Audio';
            buttonEl.disabled = false;
        } else {
            logMessage(`❌ Error: ${result.error}`);
            showToast(`Audio failed: ${result.error}`, 'error');
            buttonEl.innerHTML = originalText;
            buttonEl.disabled = false;
        }
    } catch (error) {
        logMessage(`❌ Error: ${error.message}`);
        showToast(`Audio generation error: ${error.message}`, 'error');
        buttonEl.innerHTML = originalText;
        buttonEl.disabled = false;
    }
}

// Edit section script text
function editSectionScript(sectionIndex) {
    const textEl = document.getElementById(`chunk-text-${sectionIndex}`);
    if (!textEl) {
        showToast('Could not find section text', 'error');
        return;
    }

    const currentText = textEl.textContent;
    const parent = textEl.parentElement;

    // Replace text with textarea
    const textarea = document.createElement('textarea');
    textarea.id = `edit-area-${sectionIndex}`;
    textarea.style = 'width: 100%; height: 150px; padding: 10px; background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: 6px; color: var(--text-primary); font-family: inherit; font-size: 14px; line-height: 1.6; margin-bottom: 10px;';
    textarea.value = currentText;

    const buttonContainer = document.createElement('div');
    buttonContainer.style = 'display: flex; gap: 8px; margin-bottom: 15px;';
    buttonContainer.innerHTML = `
        <button class="btn-primary" style="padding: 6px 12px; font-size: 12px;" onclick="saveSectionScript(${sectionIndex})">
            💾 Save
        </button>
        <button class="btn-secondary" style="padding: 6px 12px; font-size: 12px;" onclick="cancelSectionEdit(${sectionIndex}, '${encodeURIComponent(currentText)}')">
            ❌ Cancel
        </button>
    `;

    textEl.style.display = 'none';
    parent.insertBefore(textarea, textEl);
    parent.insertBefore(buttonContainer, textEl);
    textarea.focus();
}

// Save edited section script
function saveSectionScript(sectionIndex) {
    const textarea = document.getElementById(`edit-area-${sectionIndex}`);
    const textEl = document.getElementById(`chunk-text-${sectionIndex}`);

    if (!textarea || !textEl) {
        showToast('Could not save', 'error');
        return;
    }

    const newText = textarea.value.trim();
    if (!newText) {
        showToast('Text cannot be empty', 'error');
        return;
    }

    // Update the text element
    textEl.textContent = newText;
    textEl.style.display = '';

    // Update state
    if (state.claimScreenshots && state.claimScreenshots[sectionIndex]) {
        state.claimScreenshots[sectionIndex].chunk_text = newText;
    }

    // Update the audio button's data-text
    const audioBtn = document.getElementById(`audio-btn-${sectionIndex}`);
    if (audioBtn) {
        audioBtn.dataset.text = encodeURIComponent(newText);
    }

    // Remove textarea and button container
    textarea.remove();
    textarea.nextElementSibling?.remove();

    showToast('Section text updated! Click Regenerate Audio to create new audio.');
}

// Cancel section edit
function cancelSectionEdit(sectionIndex, originalText) {
    const textarea = document.getElementById(`edit-area-${sectionIndex}`);
    const textEl = document.getElementById(`chunk-text-${sectionIndex}`);

    if (textarea) {
        textarea.remove();
        textarea.nextElementSibling?.remove();
    }
    if (textEl) {
        textEl.style.display = '';
    }

    showToast('Edit cancelled');
}

// ============== LOAD STATE ==============

async function loadState() {
    try {
        const response = await fetch('/api/state');
        const data = await response.json();

        state.projects = data.projects || [];
        state.currentProject = data.current_project;
        state.savedVideos = data.saved_videos?.[state.currentProject] || [];

        updateProjectSelector();

        if (data.videos?.length > 0) {
            state.videos = data.videos;
            renderVideosTable(data.videos);
        }

        // Load claimScreenshots from server if available (persisted across restarts)
        if (data.claimScreenshots && data.claimScreenshots.length > 0) {
            console.log(`📸 Loading ${data.claimScreenshots.length} screenshots from server`);
            state.claimScreenshots = data.claimScreenshots;
            renderClaimScreenshots(data.claimScreenshots);
            markTabComplete(6);
        }

        renderSavedVideos();

    } catch (error) {
        console.error('Failed to load state:', error);
    }
}

// Generate and copy Editor's Brief
function copyEditorBrief() {
    if (!state.script || !state.script.raw_text) {
        showToast('No script generated', 'error');
        return;
    }

    const brief = [];
    brief.push(`🎥 EDITOR'S BRIEF: ${state.script.title || 'YouTube Script'}`);
    brief.push(`Total Words: ${state.script.total_words}`);
    brief.push('==========================================\n');

    // Process script chunks
    const chunks = state.script.raw_text.split(/\n\n+/);

    chunks.forEach((chunk, index) => {
        const lines = chunk.trim().split('\n');
        const textLines = [];
        const uris = [];

        lines.forEach(line => {
            const trimmed = line.trim();
            if (trimmed.match(/^https?:\/\//)) {
                uris.push(trimmed);
            } else if (trimmed) {
                textLines.push(trimmed);
            }
        });

        if (textLines.length === 0) return;

        const text = textLines.join(' ');
        const wordCount = text.split(/\s+/).length;
        const durationSec = Math.round(wordCount / 2.5); // ~150 wpm

        brief.push(`[SECTION ${index + 1} - ${durationSec} sec]`);
        brief.push(text);
        brief.push('');

        if (uris.length > 0) {
            brief.push('FILES TO USE:');
            uris.forEach(url => {
                // Find matching screenshot
                const screenshot = state.screenshots.find(s => s.success && s.url === url);
                brief.push(`🔗 Source: ${url}`);
                if (screenshot) {
                    brief.push(`📸 Screenshot: ${screenshot.screenshot_path}`);
                } else {
                    brief.push(`⚠️ Screenshot missing`);
                }
            });
        } else {
            brief.push('(No specific source linked)');
        }

        brief.push('\n------------------------------------------\n');
    });

    const finalContent = brief.join('\n');
    navigator.clipboard.writeText(finalContent);
    showToast('Editor\'s Brief copied to clipboard!');
}


// ============================================
// VIDEO EDITOR FUNCTIONS
// ============================================

let videoChunks = [];

async function loadVideoChunks() {
    showLoading('Loading video chunks...');
    addLog('Fetching video chunk data...', 'info');

    try {
        const response = await fetch('/api/video-chunks');
        const result = await response.json();

        if (result.success) {
            videoChunks = result.chunks;
            renderVideoTimeline(result.chunks);

            if (result.recovered) {
                showToast(`♻️ Restored ${result.total} chunks from previous session!`, 'success');
                addLog(`♻️ Restored ${result.total} chunks from previous session`, 'success');
            }

            // Show stats
            const statsDiv = document.getElementById('video-stats');
            const statsText = document.getElementById('video-stats-text');
            statsDiv.style.display = 'block';

            const withAudio = result.chunks.filter(c => c.has_audio).length;
            const withScreenshot = result.chunks.filter(c => c.has_screenshot).length;

            statsText.innerHTML = `
                <strong>Total Chunks:</strong> ${result.total} | 
                <strong>With Audio:</strong> ${withAudio} | 
                <strong>With Screenshot:</strong> ${withScreenshot} | 
                <strong>Ready for Video:</strong> ${withAudio}
            `;

            addLog(`Loaded ${result.total} chunks (${withAudio} with audio)`, 'success');
            showToast('Video chunks loaded!');
        } else {
            showToast(result.error || 'Failed to load chunks', 'error');
        }
    } catch (error) {
        addLog(`Error: ${error.message}`, 'error');
        showToast('Failed to load chunks', 'error');
    }

    hideLoading();
}

function renderVideoTimeline(chunks) {
    const container = document.getElementById('video-timeline');

    if (!chunks || chunks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">🎬</span>
                <p>No chunks available. Generate screenshots first.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = chunks.map((chunk, index) => {
        const hasVideo = chunk.has_video || chunk.custom_video_path || chunk.custom_video_url || chunk.stock_video;
        const hasVisual = chunk.has_screenshot || hasVideo;

        // Determine what to show in the preview area
        let previewContent;
        if (hasVideo && (chunk.custom_video_url || chunk.stock_video)) {
            const videoUrl = chunk.custom_video_url || chunk.stock_video;
            previewContent = `<video src="${videoUrl}" style="width: 100%; height: 100%; object-fit: cover;" muted></video>`;
        } else if (chunk.has_screenshot && chunk.screenshot_url) {
            previewContent = `<img src="${chunk.screenshot_url}" style="width: 100%; height: 100%; object-fit: cover;" />`;
        } else {
            previewContent = `<span style="font-size: 24px; opacity: 0.5;">⚠️</span>`;
        }

        return `
        <div class="video-chunk-card" data-index="${index}" style="
            background: var(--bg-secondary);
            border: 1px solid ${chunk.has_audio ? 'var(--success-color)' : 'var(--border-color)'};
            border-radius: 8px;
            overflow: hidden;
            cursor: pointer;
        " onclick="previewChunk(${index})">
            <div style="height: 80px; background: var(--bg-tertiary); display: flex; align-items: center; justify-content: center; overflow: hidden; position: relative;">
                ${previewContent}
                ${hasVideo ? '<span style="position: absolute; bottom: 4px; right: 4px; background: rgba(0,0,0,0.7); color: white; font-size: 10px; padding: 2px 4px; border-radius: 3px;">🎬</span>' : ''}
            </div>
            <div style="padding: 10px;">
                <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">
                    Chunk ${index + 1}
                </div>
                <div style="font-size: 12px; line-height: 1.4; max-height: 200px; overflow: hidden;">
                    ${chunk.text || 'No text'}
                </div>
                <div style="margin-top: 8px; display: flex; gap: 4px;">
                    <span style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: ${chunk.has_screenshot ? 'var(--success-color)' : 'var(--bg-tertiary)'}; color: ${chunk.has_screenshot ? 'white' : 'var(--text-muted)'};">
                        📷 ${chunk.has_screenshot ? '✓' : '✗'}
                    </span>
                    <span style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: ${hasVideo ? 'var(--accent)' : 'var(--bg-tertiary)'}; color: ${hasVideo ? 'white' : 'var(--text-muted)'};">
                        🎬 ${hasVideo ? '✓' : '✗'}
                    </span>
                    <span style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: ${chunk.has_audio ? 'var(--success-color)' : 'var(--bg-tertiary)'}; color: ${chunk.has_audio ? 'white' : 'var(--text-muted)'};">
                        🔊 ${chunk.has_audio ? '✓' : '✗'}
                    </span>
                </div>
            </div>
        </div>
    `}).join('');
}

function previewChunk(index) {
    const chunk = videoChunks[index];
    if (!chunk) return;

    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.id = 'chunk-editor-overlay';
    overlay.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 999; display: flex; align-items: center; justify-content: center;';

    // Create modal content
    const modal = document.createElement('div');
    modal.style.cssText = 'background: var(--bg-primary); padding: 24px; border-radius: 12px; max-width: 600px; width: 90%; max-height: 85vh; overflow-y: auto; position: relative;';

    modal.innerHTML = `
        <button onclick="closeChunkEditor()" style="position: absolute; top: 12px; right: 12px; background: none; border: none; font-size: 24px; cursor: pointer; color: var(--text-muted);">✕</button>
        
        <h3 style="margin-bottom: 16px;">📝 Chunk ${index + 1} Editor</h3>
        
        <div style="margin-bottom: 16px;">
            <label style="font-weight: 600; display: block; margin-bottom: 6px;">✏️ Chunk Text</label>
            <textarea id="chunk-text-editor-${index}" 
                style="width: 100%; min-height: 100px; padding: 12px; background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 8px; font-size: 14px; line-height: 1.5; color: var(--text-primary); resize: vertical;"
            >${chunk.full_text || chunk.text}</textarea>
            <div style="margin-top: 8px; display: flex; gap: 8px; align-items: center;">
                <button class="btn-primary" onclick="saveChunkText(${index})" style="font-size: 13px;">
                    💾 Save Text
                </button>
                <span id="chunk-text-status-${index}" style="font-size: 12px; color: var(--text-muted);"></span>
            </div>
        </div>
        
        <div style="margin-bottom: 16px;">
            <h4 style="margin-bottom: 8px;">📷 Screenshot</h4>
            <div id="chunk-screenshot-preview" style="border: 2px dashed var(--border-color); border-radius: 8px; padding: 16px; text-align: center; min-height: 150px;">
                ${chunk.has_screenshot && chunk.screenshot_url
            ? `<img src="${chunk.screenshot_url}" style="max-width: 100%; max-height: 300px; border-radius: 8px;" />`
            : `<p style="color: var(--text-muted);">⚠️ No screenshot - will use placeholder</p>`
        }
            </div>
            <div style="margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap;">
                <label class="btn-secondary" style="cursor: pointer; display: inline-flex; align-items: center; gap: 6px;">
                    📤 Upload Screenshot
                    <input type="file" accept="image/*" onchange="uploadChunkScreenshot(${index}, this)" style="display: none;">
                </label>
                <label class="btn-secondary" style="cursor: pointer; display: inline-flex; align-items: center; gap: 6px; border-color: var(--accent);">
                    🎬 Upload Video
                    <input type="file" accept="video/*" onchange="uploadChunkVideo(${index}, this)" style="display: none;">
                </label>
                <button class="btn-secondary" onclick="usePreviousScreenshot(${index})">
                    ⬅️ Use Previous
                </button>
                <button class="btn-secondary" onclick="regenerateChunkScreenshot(${index})" style="background: var(--bg-tertiary);" title="Try next search result">
                    🔄 Regenerate
                </button>
            </div>
            <div style="margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
                <label style="color: var(--text-secondary); font-size: 13px;">Stock Video:</label>
                <select id="positive-video-select-${index}" onchange="selectStockVideo(${index}, 'positive', this.value)" style="padding: 6px 10px; background: var(--bg-tertiary); border: 1px solid var(--success); border-radius: 6px; color: var(--text-primary); font-size: 12px;">
                    <option value="">➕ Positive</option>
                </select>
                <select id="negative-video-select-${index}" onchange="selectStockVideo(${index}, 'negative', this.value)" style="padding: 6px 10px; background: var(--bg-tertiary); border: 1px solid var(--error); border-radius: 6px; color: var(--text-primary); font-size: 12px;">
                    <option value="">➖ Negative</option>
                </select>
                <button class="btn-secondary" onclick="loadStockVideoOptions(${index})" style="font-size: 11px; padding: 4px 8px;">🔄</button>
            </div>
            <div id="stock-video-indicator-${index}"></div>
        </div>
        
        <div style="margin-bottom: 16px;">
            <h4 style="margin-bottom: 8px;">🔊 Audio</h4>
            <div id="chunk-audio-player-${index}">
            ${chunk.has_audio && chunk.audio_url
            ? `<audio controls src="${chunk.audio_url}" style="width: 100%;"></audio>`
            : `<p style="color: var(--text-muted);">No audio generated yet.</p>`
        }
            </div>
            <div style="margin-top: 8px;">
                <button class="btn-secondary" onclick="regenerateChunkAudio(${index})" style="display: inline-flex; align-items: center; gap: 6px;">
                    🔄 Regenerate Audio
                </button>
            </div>
        </div>
        
        <div style="display: flex; gap: 8px; justify-content: flex-end;">
            <button class="btn-secondary" onclick="closeChunkEditor()">Close</button>
        </div>
    `;

    overlay.appendChild(modal);
    overlay.onclick = (e) => { if (e.target === overlay) closeChunkEditor(); };
    document.body.appendChild(overlay);

    // Auto-load stock video options and show existing selections
    loadStockVideoOptions(index);
    updateStockVideoIndicator(index);
}

function closeChunkEditor() {
    const overlay = document.getElementById('chunk-editor-overlay');
    if (overlay) {
        document.body.removeChild(overlay);
    }
}

function saveChunkText(chunkIndex) {
    const textarea = document.getElementById(`chunk-text-editor-${chunkIndex}`);
    const statusSpan = document.getElementById(`chunk-text-status-${chunkIndex}`);

    if (!textarea) {
        showToast('Text editor not found', 'error');
        return;
    }

    const newText = textarea.value.trim();
    if (!newText) {
        showToast('Text cannot be empty', 'error');
        return;
    }

    // Update chunk in memory
    if (videoChunks[chunkIndex]) {
        videoChunks[chunkIndex].text = newText.substring(0, 100);  // Short preview
        videoChunks[chunkIndex].full_text = newText;

        // Re-render timeline to show updated text
        renderVideoTimeline(videoChunks);

        // Show confirmation
        if (statusSpan) {
            statusSpan.innerHTML = '✅ Saved!';
            statusSpan.style.color = 'var(--success-color)';
            setTimeout(() => {
                statusSpan.innerHTML = '';
            }, 3000);
        }

        showToast(`✅ Text updated for chunk ${chunkIndex + 1}`);
        addLog(`📝 Updated text for chunk ${chunkIndex + 1}`, 'success');
    }
}

async function regenerateChunkAudio(chunkIndex) {
    const chunk = videoChunks[chunkIndex];
    if (!chunk) {
        showToast('Chunk not found', 'error');
        return;
    }

    const text = chunk.full_text || chunk.text;
    if (!text) {
        showToast('No text for this chunk', 'error');
        return;
    }

    showLoading(`Generating audio for chunk ${chunkIndex + 1}...`);

    try {
        const response = await fetch('/api/regenerate-chunk-audio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: text,
                chunk_index: chunkIndex
            })
        });

        const result = await response.json();

        if (result.success) {
            // Update chunk in memory
            videoChunks[chunkIndex].has_audio = true;
            videoChunks[chunkIndex].audio_url = result.audio_url;

            // Update the audio player in the modal
            const playerContainer = document.getElementById(`chunk-audio-player-${chunkIndex}`);
            if (playerContainer) {
                playerContainer.innerHTML = `<audio controls src="${result.audio_url}?t=${Date.now()}" style="width: 100%;"></audio>`;
            }

            // Re-render timeline to show updated status
            renderVideoTimeline(videoChunks);

            showToast(`✅ Audio generated for chunk ${chunkIndex + 1}`);
            addLog(`🔊 Regenerated audio for chunk ${chunkIndex + 1}`, 'success');
        } else {
            showToast(result.error || 'Failed to generate audio', 'error');
        }
    } catch (error) {
        showToast('Audio generation failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

async function uploadChunkScreenshot(chunkIndex, input) {
    const file = input.files[0];
    if (!file) return;

    showLoading('Uploading screenshot...');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('chunk_index', chunkIndex);

    try {
        const response = await fetch('/api/upload-chunk-screenshot', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            showToast('Screenshot uploaded successfully!');
            // Update the preview in the modal
            const previewDiv = document.getElementById('chunk-screenshot-preview');
            if (previewDiv) {
                previewDiv.innerHTML = `<img src="${result.screenshot_url}" style="max-width: 100%; max-height: 300px; border-radius: 8px;" />`;
            }
            // Update videoChunks array
            if (videoChunks[chunkIndex]) {
                videoChunks[chunkIndex].has_screenshot = true;
                videoChunks[chunkIndex].screenshot_url = result.screenshot_url;
            }
            // Refresh the timeline
            renderVideoTimeline(videoChunks);
        } else {
            showToast(result.error || 'Upload failed', 'error');
        }
    } catch (error) {
        showToast('Upload failed: ' + error.message, 'error');
    }

    hideLoading();
}

// Upload custom video for a specific chunk
async function uploadChunkVideo(chunkIndex, input) {
    const file = input.files[0];
    if (!file) return;

    showLoading('Uploading video...');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('chunk_index', chunkIndex);

    try {
        const response = await fetch('/api/upload-chunk-video', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            showToast('Video uploaded successfully!');

            // Update the chunk's custom video
            if (videoChunks[chunkIndex]) {
                videoChunks[chunkIndex].custom_video_path = result.video_path;
                videoChunks[chunkIndex].custom_video_url = result.video_url;
                videoChunks[chunkIndex].has_video = true;  // Mark as having video
            }

            // Show video preview in the indicator area
            const indicator = document.getElementById(`stock-video-indicator-${chunkIndex}`);
            if (indicator) {
                indicator.innerHTML = `
                    <div style="margin-top: 12px; padding: 12px; background: var(--bg-tertiary); border-radius: 8px;">
                        <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px;">
                            <strong>Uploaded Video:</strong> 🎬 ${file.name}
                        </div>
                        <video 
                            src="${result.video_url}" 
                            style="width: 100%; max-height: 200px; border-radius: 6px; background: #000;"
                            controls
                            muted
                            preload="metadata"
                        ></video>
                        <p style="font-size: 11px; color: var(--text-muted); margin-top: 6px;">
                            ℹ️ This video will be used for this chunk in the final video.
                        </p>
                    </div>
                `;
            }

            renderVideoTimeline(videoChunks);
            updateVideoStats();  // Update the stats display
        } else {
            showToast(result.error || 'Upload failed', 'error');
        }
    } catch (error) {
        showToast('Upload failed: ' + error.message, 'error');
    }

    hideLoading();
}

// Update video stats display
function updateVideoStats() {
    const statsDiv = document.getElementById('video-stats');
    const statsText = document.getElementById('video-stats-text');

    if (!statsDiv || !statsText || !videoChunks) return;

    statsDiv.style.display = 'block';

    const withAudio = videoChunks.filter(c => c.has_audio).length;
    const withScreenshot = videoChunks.filter(c => c.has_screenshot).length;
    const withVideo = videoChunks.filter(c => c.has_video || c.custom_video_path || c.custom_video_url || c.stock_video).length;

    statsText.innerHTML = `
        <strong>Total Chunks:</strong> ${videoChunks.length} | 
        <strong>With Audio:</strong> ${withAudio} | 
        <strong>With Screenshot:</strong> ${withScreenshot} | 
        <strong>With Video:</strong> ${withVideo} | 
        <strong>Ready for Video:</strong> ${withAudio}
    `;
}

// Use screenshot from previous chunk (cascade back if empty)
async function usePreviousScreenshot(chunkIndex) {
    if (chunkIndex === 0) {
        showToast('No previous chunk available', 'error');
        return;
    }

    // Find the nearest previous chunk with a screenshot
    let sourceIndex = chunkIndex - 1;
    while (sourceIndex >= 0 && !videoChunks[sourceIndex]?.has_screenshot) {
        sourceIndex--;
    }

    if (sourceIndex < 0) {
        showToast('No previous screenshot found to use', 'error');
        return;
    }

    showLoading('Copying screenshot from chunk ' + (sourceIndex + 1) + '...');

    try {
        const response = await fetch('/api/copy-chunk-screenshot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source_index: sourceIndex,
                target_index: chunkIndex
            })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`Screenshot copied from chunk ${sourceIndex + 1}`);
            videoChunks[chunkIndex].has_screenshot = true;
            videoChunks[chunkIndex].screenshot_url = result.screenshot_url;

            // Update preview in modal
            const previewDiv = document.getElementById('chunk-screenshot-preview');
            if (previewDiv) {
                previewDiv.innerHTML = `<img src="${result.screenshot_url}" style="max-width: 100%; max-height: 300px; border-radius: 8px;" />`;
            }

            renderVideoTimeline(videoChunks);
        } else {
            showToast(result.error || 'Failed to copy screenshot', 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }

    hideLoading();
}

// Regenerate screenshot using next available Serper result
// Tracks which result index to try (0=1st, 1=2nd, 2=3rd, etc.)
const regenerateResultIndex = {};

async function regenerateChunkScreenshot(chunkIndex) {
    // Track which result index to try next
    if (regenerateResultIndex[chunkIndex] === undefined) {
        regenerateResultIndex[chunkIndex] = 1; // Start with 2nd result (index 1)
    }

    const resultIndex = regenerateResultIndex[chunkIndex];

    showLoading(`Trying search result ${resultIndex + 1}...`);

    try {
        const response = await fetch('/api/regenerate-chunk-screenshot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chunk_index: chunkIndex,
                result_index: resultIndex,
                allow_duplicates: true
            })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`Screenshot from result ${resultIndex + 1} of ${result.available_results}`);
            videoChunks[chunkIndex].has_screenshot = true;
            videoChunks[chunkIndex].screenshot_url = result.screenshot_url;

            // Move to next result for future regeneration
            regenerateResultIndex[chunkIndex] = (resultIndex + 1) % (result.available_results || 3);

            // Update preview in modal
            const previewDiv = document.getElementById('chunk-screenshot-preview');
            if (previewDiv) {
                previewDiv.innerHTML = `<img src="${result.screenshot_url}" style="max-width: 100%; max-height: 300px; border-radius: 8px;" />`;
            }

            renderVideoTimeline(videoChunks);
        } else {
            showToast(result.error || 'No more results available', 'error');
            // Reset to try first result again
            regenerateResultIndex[chunkIndex] = 0;
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }

    hideLoading();
}

async function loadStockVideoOptions(chunkIndex) {
    try {
        const response = await fetch('/api/stock-videos');
        const result = await response.json();

        if (result.success) {
            // Populate positive dropdown
            const posSelect = document.getElementById(`positive-video-select-${chunkIndex}`);
            if (posSelect) {
                posSelect.innerHTML = '<option value="">➕ Positive</option>';
                result.positive.forEach((video, i) => {
                    posSelect.innerHTML += `<option value="${video}">${i + 1}. ${video}</option>`;
                });
            }

            // Populate negative dropdown
            const negSelect = document.getElementById(`negative-video-select-${chunkIndex}`);
            if (negSelect) {
                negSelect.innerHTML = '<option value="">➖ Negative</option>';
                result.negative.forEach((video, i) => {
                    negSelect.innerHTML += `<option value="${video}">${i + 1}. ${video}</option>`;
                });
            }

            showToast(`Found ${result.positive.length} positive, ${result.negative.length} negative videos`);
        } else {
            showToast(result.error || 'Failed to load stock videos', 'error');
        }
    } catch (error) {
        showToast('Error loading stock videos: ' + error.message, 'error');
    }
}

// Select a stock video for a chunk
function selectStockVideo(chunkIndex, type, filename) {
    if (!filename) {
        // User cleared selection
        if (videoChunks[chunkIndex]?.stock_videos) {
            delete videoChunks[chunkIndex].stock_videos[type];
        }
        updateStockVideoIndicator(chunkIndex);
        return;
    }

    // Store selection in chunk data
    if (!videoChunks[chunkIndex].stock_videos) {
        videoChunks[chunkIndex].stock_videos = {};
    }
    videoChunks[chunkIndex].stock_videos[type] = filename;

    // Update visual indicator
    updateStockVideoIndicator(chunkIndex);

    showToast(`✅ ${type.charAt(0).toUpperCase() + type.slice(1)} video selected: ${filename}`);
}

// Show what stock videos are selected for this chunk - with video preview
function updateStockVideoIndicator(chunkIndex) {
    const indicator = document.getElementById(`stock-video-indicator-${chunkIndex}`);
    if (!indicator) return;

    const stocks = videoChunks[chunkIndex]?.stock_videos || {};

    // Determine which stock video to show (prefer negative, then positive)
    let selectedVideo = null;
    let selectedType = null;

    if (stocks.negative) {
        selectedVideo = stocks.negative;
        selectedType = 'negative';
    } else if (stocks.positive) {
        selectedVideo = stocks.positive;
        selectedType = 'positive';
    }

    if (selectedVideo) {
        const videoUrl = `/api/stock-video/${selectedType}/${selectedVideo}`;
        indicator.innerHTML = `
            <div style="margin-top: 12px; padding: 12px; background: var(--bg-tertiary); border-radius: 8px;">
                <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px;">
                    <strong>Stock Video Preview:</strong> ${selectedType === 'positive' ? '✅' : '❌'} ${selectedVideo}
                </div>
                <video 
                    src="${videoUrl}" 
                    style="width: 100%; max-height: 200px; border-radius: 6px; background: #000;"
                    controls
                    muted
                    preload="metadata"
                ></video>
                <p style="font-size: 11px; color: var(--text-muted); margin-top: 6px;">
                    ℹ️ This video will replace the screenshot in the final video.
                </p>
            </div>
        `;
    } else {
        indicator.innerHTML = '';
    }
}

async function generateAllAudio() {
    showLoading('Generating audio for all chunks (this may take a while)...');
    addLog('Starting batch TTS generation...', 'info');

    try {
        const response = await fetch('/api/generate-all-audio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const result = await response.json();

        if (result.success) {
            addLog(result.message, 'success');
            showToast(result.message);

            // Reload chunks to show updated status
            await loadVideoChunks();
        } else {
            addLog(`Error: ${result.error}`, 'error');
            showToast(result.error || 'Failed to generate audio', 'error');
        }
    } catch (error) {
        addLog(`Error: ${error.message}`, 'error');
        showToast('Failed to generate audio', 'error');
    }

    hideLoading();
}

async function buildVideo() {
    showLoading('Building video (this may take several minutes)...');
    addLog('Starting video assembly...', 'info');

    try {
        // Send chunk data including stock video selections
        const response = await fetch('/api/build-video', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chunks: videoChunks.map((chunk, i) => ({
                    index: i,
                    stock_videos: chunk.stock_videos || {}
                }))
            })
        });

        const result = await response.json();

        if (result.success) {
            addLog(result.message, 'success');
            showToast('Video built successfully!');

            // Show video preview
            const previewDiv = document.getElementById('video-preview');
            const videoSource = document.getElementById('video-source');
            const downloadLink = document.getElementById('video-download');

            videoSource.src = result.video_url;
            downloadLink.href = result.video_url;
            previewDiv.style.display = 'block';

            // Reload video element
            videoSource.parentElement.load();

            addLog(`Video: ${result.segments_count} segments, ${(result.duration / 60).toFixed(1)} min`, 'success');

            // Show/enable subtitle button
            const subtitleBtn = document.getElementById('add-subtitles-btn');
            if (subtitleBtn) {
                subtitleBtn.style.display = 'inline-block';
                subtitleBtn.disabled = false;
            }
        } else {
            addLog(`Error: ${result.error}`, 'error');
            showToast(result.error || 'Failed to build video', 'error');
        }
    } catch (error) {
        addLog(`Error: ${error.message}`, 'error');
        showToast('Failed to build video', 'error');
    }

    hideLoading();
}

async function generateSubtitles() {
    showLoading('Generating subtitles (transcribing audio + burning into video)...');
    addLog('Starting subtitle generation...', 'info');

    try {
        const response = await fetch('/api/add-subtitles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})  // Uses latest video
        });

        const result = await response.json();

        if (result.success) {
            addLog('Subtitles generated and burned successfully!', 'success');
            showToast('Subtitled video ready!');

            // Update video preview to show subtitled version
            const videoSource = document.getElementById('video-source');
            const downloadLink = document.getElementById('video-download');

            if (result.subtitled_video) {
                videoSource.src = result.subtitled_video;
                downloadLink.href = result.subtitled_video;
                videoSource.parentElement.load();

                addLog(`Subtitled video: ${result.subtitled_video}`, 'success');
            }

            // Store SRT path for download
            if (result.srt_file) {
                state.lastSrtPath = result.srt_file;
            }

            // Show additional buttons
            const subtitleBtn = document.getElementById('add-subtitles-btn');
            const srtBtn = document.getElementById('download-srt-btn');
            const chaptersBtn = document.getElementById('generate-description-btn');

            if (subtitleBtn) {
                subtitleBtn.textContent = '✅ Subtitles Added';
                subtitleBtn.disabled = true;
            }
            if (srtBtn) srtBtn.style.display = 'inline-block';
            if (chaptersBtn) chaptersBtn.style.display = 'inline-block';
        } else {
            addLog(`Subtitle error: ${result.error}`, 'error');
            showToast(result.error || 'Failed to generate subtitles', 'error');
        }
    } catch (error) {
        addLog(`Error: ${error.message}`, 'error');
        showToast('Failed to generate subtitles', 'error');
    }

    hideLoading();
}


// Download the generated SRT file
async function downloadGeneratedSRT() {
    try {
        const response = await fetch('/api/download-srt');
        if (!response.ok) {
            showToast('No SRT file available', 'error');
            return;
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'subtitles.srt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast('SRT downloaded!');
    } catch (error) {
        showToast('Failed to download SRT', 'error');
    }
}


// Generate timestamped chapters from narrative beats
function generateVideoDescription() {
    const beats = state.narrativeBeats || [];

    if (beats.length === 0) {
        // Fall back to script chunks if no narrative beats
        if (state.script?.raw_text) {
            generateChaptersFromScript();
            return;
        }
        showToast('No script beats available. Generate a narrative script first.', 'error');
        return;
    }

    // Calculate timestamps based on word counts (~150 words per minute)
    let currentSeconds = 0;
    let chapters = [];

    for (const beat of beats) {
        const timeStr = formatTimestamp(currentSeconds);
        chapters.push(`${timeStr} ${beat.name}`);

        // Advance time based on word count
        const durationSeconds = Math.round((beat.word_count || beat.word_target) / 150 * 60);
        currentSeconds += durationSeconds;
    }

    const chaptersText = chapters.join('\n');

    // Display in UI
    const output = document.getElementById('chapters-output');
    const textEl = document.getElementById('chapters-text');
    if (output && textEl) {
        textEl.textContent = chaptersText;
        output.style.display = 'block';
    }

    showToast('Chapters generated!');
}


function generateChaptersFromScript() {
    // Fallback: create rough chapters from script chunks
    const chunks = state.script?.narrative_beats || [];
    if (chunks.length === 0) {
        showToast('No script data available', 'error');
        return;
    }
    generateVideoDescription();
}


function formatTimestamp(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = Math.floor(totalSeconds % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}


function copyChaptersToClipboard() {
    const textEl = document.getElementById('chapters-text');
    if (textEl) {
        navigator.clipboard.writeText(textEl.textContent)
            .then(() => showToast('Chapters copied to clipboard!'))
            .catch(() => showToast('Failed to copy', 'error'));
    }
}

// ============== VIDEO SELECTOR FUNCTIONS ==============

let selectedVideoFilename = null;

async function loadVideoList() {
    try {
        const response = await fetch('/api/list-videos');
        const result = await response.json();

        const selector = document.getElementById('video-selector');
        selector.innerHTML = '<option value="">-- Select a video --</option>';

        if (result.success && result.videos.length > 0) {
            for (const video of result.videos) {
                const label = video.is_subtitled ? '📝 ' : '';
                const option = document.createElement('option');
                option.value = video.filename;
                option.textContent = `${label}${video.filename} (${video.size_mb} MB)`;
                selector.appendChild(option);
            }
            showToast(`Loaded ${result.count} videos`);
        } else {
            showToast('No videos found', 'error');
        }
    } catch (error) {
        showToast('Failed to load video list', 'error');
    }
}

function loadSelectedVideo() {
    const selector = document.getElementById('video-selector');
    const filename = selector.value;

    if (!filename) {
        showToast('Select a video first', 'error');
        return;
    }

    selectedVideoFilename = filename;

    // Show video preview
    const previewDiv = document.getElementById('video-preview');
    const videoSource = document.getElementById('video-source');
    const downloadLink = document.getElementById('video-download');

    videoSource.src = `/api/video/${filename}`;
    downloadLink.href = `/api/video/${filename}`;
    previewDiv.style.display = 'block';
    videoSource.parentElement.load();

    showToast(`Loaded: ${filename}`);
    addLog(`Loaded video: ${filename}`, 'success');
}

async function addSubtitlesToSelected() {
    const selector = document.getElementById('video-selector');
    const filename = selector.value;

    if (!filename) {
        showToast('Select a video first', 'error');
        return;
    }

    // Don't process already subtitled videos
    if (filename.includes('_subtitled')) {
        showToast('This video already has subtitles', 'error');
        return;
    }

    showLoading('Generating subtitles (transcribing + burning)...');
    addLog(`Adding subtitles to: ${filename}`, 'info');

    try {
        const response = await fetch('/api/add-subtitles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_filename: filename })
        });

        const result = await response.json();

        if (result.success) {
            addLog('Subtitles burned successfully!', 'success');
            showToast('Subtitled video ready!');

            // Update video preview to show subtitled version
            const videoSource = document.getElementById('video-source');
            const downloadLink = document.getElementById('video-download');

            if (result.subtitled_video) {
                videoSource.src = result.subtitled_video;
                downloadLink.href = result.subtitled_video;
                videoSource.parentElement.load();
                document.getElementById('video-preview').style.display = 'block';

                addLog(`Subtitled video: ${result.subtitled_video}`, 'success');
            }

            // Refresh video list to show new subtitled video
            await loadVideoList();
        } else {
            addLog(`Subtitle error: ${result.error}`, 'error');
            showToast(result.error || 'Failed to generate subtitles', 'error');
        }
    } catch (error) {
        addLog(`Error: ${error.message}`, 'error');
        showToast('Failed to generate subtitles', 'error');
    }

    hideLoading();
}

// Auto-load video list when page loads (for Step 7)
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => loadVideoList(), 1000);
});

async function clearAllAudio() {
    if (!confirm('Are you sure you want to delete all audio files? Screenshots will not be affected.')) {
        return;
    }

    showLoading('Clearing audio files...');
    addLog('Deleting all audio files...', 'info');

    try {
        const response = await fetch('/api/clear-audio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const result = await response.json();

        if (result.success) {
            addLog(result.message, 'success');
            showToast(result.message);

            // Reload chunks to show updated status
            await loadVideoChunks();
        } else {
            addLog(`Error: ${result.error}`, 'error');
            showToast(result.error || 'Failed to clear audio', 'error');
        }
    } catch (error) {
        addLog(`Error: ${error.message}`, 'error');
        showToast('Failed to clear audio', 'error');
    }

    hideLoading();
}

// ============== THUMBNAIL GENERATOR ==============

let selectedThumbnailVideo = null;
let thumbnailAnalysis = null;
let cachedSavedVideos = []; // Global cache for video data

async function loadSavedVideosForThumbnail() {
    showLoading('Loading saved videos...');

    try {
        const response = await fetch('/api/get-saved-videos');
        const result = await response.json();

        if (result.success) {
            cachedSavedVideos = result.videos;

            if (result.videos.length > 0) {
                renderThumbnailVideosGrid(result.videos);
                showToast(`Loaded ${result.videos.length} saved videos`);
            } else {
                document.getElementById('thumbnail-videos-grid').innerHTML = `
                    <div class="empty-state">
                        <span class="empty-icon">📭</span>
                        <p>No saved videos found. Save videos from the Discovery tab first.</p>
                    </div>
                `;
            }

            // Auto-fill topic if context available
            if (result.context && result.context.topic) {
                const topicInput = document.getElementById('thumbnail-topic');
                if (topicInput && !topicInput.value) {
                    topicInput.value = result.context.topic;
                    addLog(`Auto-filled topic: ${result.context.topic}`, 'info');
                }
            }
        }
    } catch (error) {
        showToast('Failed to load saved videos', 'error');
        console.error(error);
    }

    hideLoading();
}

function renderThumbnailVideosGrid(videos) {
    const grid = document.getElementById('thumbnail-videos-grid');
    grid.innerHTML = videos.map((video, index) => `
        <div class="thumbnail-card" onclick="selectThumbnailVideoByIndex(${index})"
            style="cursor: pointer; border-radius: 8px; overflow: hidden; background: var(--bg-secondary); transition: transform 0.2s; position: relative; ${selectedThumbnailVideo === video.video_id ? 'border: 3px solid var(--primary-color); box-shadow: 0 0 10px rgba(var(--primary-rgb), 0.5);' : 'border: 1px solid transparent;'}">
            <div style="position: relative; width: 100%; padding-top: 56.25%;">
                <img src="${video.thumbnail_url || `https://img.youtube.com/vi/${video.video_id}/mqdefault.jpg`}" 
                     style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover;"
                     onerror="this.src='https://placehold.co/320x180/333/white?text=No+Thumb'">
            </div>
            <div style="padding: 10px; font-size: 13px; line-height: 1.4; font-weight: 500;">
                ${video.title.substring(0, 60)}${video.title.length > 60 ? '...' : ''}
            </div>
            ${selectedThumbnailVideo === video.video_id ? '<div style="position: absolute; top: 5px; right: 5px; background: var(--primary-color); color: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center;">✓</div>' : ''}
        </div>
    `).join('');
}

function selectThumbnailVideoByIndex(index) {
    const video = cachedSavedVideos[index];
    if (!video) return;

    selectThumbnailVideo(video.video_id, video.title, video.thumbnail_url);

    // Re-render to show selection highlight
    renderThumbnailVideosGrid(cachedSavedVideos);
}

function selectThumbnailVideo(videoId, title, thumbnailUrl) {
    selectedThumbnailVideo = videoId;

    // Show analysis section
    document.getElementById('thumbnail-analysis-section').style.display = 'block';

    const thumbImg = document.getElementById('selected-thumbnail');
    thumbImg.src = thumbnailUrl || `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`;
    thumbImg.onerror = function () { this.src = 'https://placehold.co/320x180/333/white?text=No+Thumb'; };

    document.getElementById('selected-video-title').textContent = title;
    document.getElementById('thumbnail-style-analysis').innerHTML = '<p style="color: var(--text-muted); font-style: italic;">Click "Analyze Style" to get AI breakdown</p>';

    // Scroll to analysis section
    document.getElementById('thumbnail-analysis-section').scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Reset analysis
    thumbnailAnalysis = null;

    showToast(`Selected: ${title.substring(0, 30)}...`);
}

// Store the current dissection data
let currentDissection = null;

async function analyzeThumbnail() {
    if (!selectedThumbnailVideo) {
        showToast('Please select a video first', 'error');
        return;
    }

    showLoading('Analyzing thumbnail - dissecting into components...');
    addLog('Dissecting thumbnail with Gemini Vision...', 'info');

    try {
        const response = await fetch('/api/analyze-thumbnail', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_id: selectedThumbnailVideo })
        });

        const result = await response.json();

        if (result.success && result.dissection) {
            currentDissection = result.dissection;

            // Populate the dissection form
            populateDissectionForm(result.dissection);

            // Show the form
            document.getElementById('dissection-form').style.display = 'block';
            document.getElementById('dissection-form').scrollIntoView({ behavior: 'smooth', block: 'start' });

            showToast('Thumbnail dissected into 5 components!');
            addLog('Dissection complete - edit fields and generate', 'success');
        } else {
            showToast(result.error || 'Dissection failed', 'error');
            addLog(`Error: ${result.error}`, 'error');
            if (result.raw) {
                console.log('Raw response:', result.raw);
            }
        }
    } catch (error) {
        showToast('Failed to analyze thumbnail', 'error');
        addLog(`Error: ${error.message}`, 'error');
    }

    hideLoading();
}

function populateDissectionForm(dissection) {
    // 1. Person
    const personDesc = dissection.person?.description || 'No person detected';
    document.getElementById('dissect-person-original').textContent = personDesc;

    // 2. Expression
    const exprDesc = dissection.expression?.description || 'N/A';
    const emotion = dissection.expression?.emotion || '';
    document.getElementById('dissect-expression-original').textContent =
        emotion ? `${emotion} - ${exprDesc}` : exprDesc;

    // 3. Text
    const textArr = dissection.text || [];
    const textContents = textArr.map(t => t.content).join(' | ');
    document.getElementById('dissect-text-original').textContent = textContents || 'No text detected';

    // 4. Colors
    const colors = dissection.colors || {};
    const colorsContainer = document.getElementById('dissect-colors-original');
    colorsContainer.innerHTML = '';
    ['primary', 'secondary', 'accent'].forEach(key => {
        if (colors[key]) {
            colorsContainer.innerHTML += `
                <div style="display: flex; align-items: center; gap: 4px;">
                    <div style="width: 20px; height: 20px; background: ${colors[key]}; border-radius: 4px; border: 1px solid #fff;"></div>
                    <span style="font-size: 12px;">${colors[key]}</span>
                </div>
            `;
        }
    });

    // 5. Graphics
    const graphicsDesc = dissection.graphics?.description || 'No graphics detected';
    const elements = dissection.graphics?.elements || [];
    document.getElementById('dissect-graphics-original').textContent =
        elements.length > 0 ? `${graphicsDesc} (${elements.join(', ')})` : graphicsDesc;

    // Clear override fields
    document.getElementById('dissect-person-override').value = '';
    document.getElementById('dissect-expression-override').value = '';
    document.getElementById('dissect-text-override').value = '';
    document.getElementById('dissect-colors-override').value = '';
    document.getElementById('dissect-graphics-override').value = '';
}

async function generateThumbnailFromDissection() {
    if (!selectedThumbnailVideo) {
        showToast('Please select a reference video first', 'error');
        return;
    }

    if (!currentDissection) {
        showToast('Please analyze the thumbnail first', 'error');
        return;
    }

    // Collect overrides from form
    const overrides = {};

    const personOverride = document.getElementById('dissect-person-override').value.trim();
    if (personOverride) overrides.person = personOverride;

    const exprOverride = document.getElementById('dissect-expression-override').value.trim();
    if (exprOverride) overrides.expression = exprOverride;

    const textOverride = document.getElementById('dissect-text-override').value.trim();
    if (textOverride) overrides.text = textOverride;

    const colorOverride = document.getElementById('dissect-colors-override').value.trim();
    if (colorOverride) overrides.colors = colorOverride;

    const graphicsOverride = document.getElementById('dissect-graphics-override').value.trim();
    if (graphicsOverride) overrides.graphics = graphicsOverride;

    showLoading('Generating thumbnail with your specifications...');
    addLog(`Generating thumbnail with ${Object.keys(overrides).length} overrides...`, 'info');
    if (overrides.text) addLog(`New text: "${overrides.text}"`, 'info');

    try {
        const response = await fetch('/api/generate-thumbnail-image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                video_id: selectedThumbnailVideo,
                original: currentDissection,
                overrides: overrides
            })
        });

        const result = await response.json();

        if (result.success) {
            // Add cache-busting timestamp to prevent showing cached old image
            const cacheBuster = `?t=${Date.now()}`;
            document.getElementById('generated-thumbnail-img').src = result.image_url + cacheBuster;
            document.getElementById('download-thumbnail-link').href = result.image_url;
            document.getElementById('generated-thumbnail-section').style.display = 'block';
            document.getElementById('generated-thumbnail-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
            showToast('Thumbnail generated!');
            addLog('Thumbnail generated successfully!', 'success');
            addLog(`Image URL: ${result.image_url}`, 'info');
        } else {
            showToast(result.error || 'Failed to generate thumbnail', 'error');
            addLog(`Error: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Failed to generate thumbnail', 'error');
        addLog(`Error: ${error.message}`, 'error');
    }

    hideLoading();
}

// ============== TITLE GENERATOR ==============

let selectedInspirationTitle = '';
let cachedTitleVideos = [];

async function loadSavedVideosForTitle() {
    showLoading('Loading saved videos for titles...');

    try {
        const response = await fetch('/api/get-saved-videos');
        const result = await response.json();

        if (result.success) {
            cachedTitleVideos = result.videos;

            // Auto-fill topic and outline
            if (result.context) {
                if (result.context.topic) {
                    const topicInput = document.getElementById('title-topic');
                    if (topicInput && !topicInput.value) topicInput.value = result.context.topic;
                }
                if (result.context.summary) {
                    const outlineInput = document.getElementById('title-outline');
                    if (outlineInput && !outlineInput.value) outlineInput.value = result.context.summary.substring(0, 500) + '...';
                }
            }

            if (result.videos.length > 0) {
                renderTitleInspirationOptions(result.videos);
                showToast(`Loaded ${result.videos.length} saved videos`);
            } else {
                document.getElementById('title-inspiration-options').innerHTML = `
                    <p style="color: var(--text-muted);">No saved videos found. Save videos from the Discovery tab first.</p>
                `;
            }
        }
    } catch (error) {
        showToast('Failed to load saved videos', 'error');
    }

    hideLoading();
}

function renderTitleInspirationOptions(videos) {
    const container = document.getElementById('title-inspiration-options');
    container.innerHTML = videos.map((video, index) => `
        <label style="display: flex; align-items: center; gap: 10px; padding: 12px; border-radius: 8px; cursor: pointer; transition: background 0.2s; margin-bottom: 8px; background: var(--bg-tertiary);"
            onmouseover="this.style.background='var(--bg-primary)'" onmouseout="this.style.background='var(--bg-tertiary)'">
            <input type="radio" name="inspiration-title" value="${index}" 
                onchange="selectInspirationTitleByIndex(this.value)" style="width: 18px; height: 18px; cursor: pointer;">
            <span style="flex: 1; font-weight: 500;">${video.title}</span>
        </label>
    `).join('');
}

function selectInspirationTitleByIndex(index) {
    const video = cachedTitleVideos[index];
    if (video) {
        selectedInspirationTitle = video.title;
        showToast(`Selected inspiration: "${video.title.substring(0, 30)}..."`);
    }
}

// ============== KEYWORD RESEARCH ==============

async function researchKeywords() {
    const seedKeyword = document.getElementById('keyword-seed').value.trim();
    const region = document.getElementById('keyword-region').value;

    if (!seedKeyword) {
        showToast('Please enter a seed keyword', 'error');
        return;
    }

    showLoading(`Researching keywords in ${region}...`);
    addLog(`Researching: ${seedKeyword} (Region: ${region})`, 'info');

    try {
        const response = await fetch('/api/keyword-research', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                keyword: seedKeyword,
                include_suggestions: true,
                region: region
            })
        });

        const result = await response.json();

        if (result.success) {
            // Store for export
            lastKeywordResults = result;

            // Show seed result
            const seedResult = result.seed_result;
            const seedContent = document.getElementById('keyword-seed-content');
            const difficultyColor = getDifficultyColor(seedResult.difficulty_level);
            const multiplierColor = seedResult.multiplier >= 5 ? 'var(--success-color)' : seedResult.multiplier >= 2 ? 'var(--warning-color)' : 'var(--text-muted)';

            seedContent.innerHTML = `
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 16px; margin-bottom: 12px;">
                    <div style="text-align: center; padding: 12px; background: var(--bg-tertiary); border-radius: 8px;">
                        <div style="font-size: 24px; font-weight: bold; color: ${difficultyColor};">${seedResult.difficulty_score}</div>
                        <div style="font-size: 12px; color: var(--text-muted);">Difficulty</div>
                    </div>
                    <div style="text-align: center; padding: 12px; background: var(--bg-tertiary); border-radius: 8px;">
                        <div style="font-size: 24px; font-weight: bold;">${formatNumber(seedResult.avg_views)}</div>
                        <div style="font-size: 12px; color: var(--text-muted);">Avg Views</div>
                    </div>
                    <div style="text-align: center; padding: 12px; background: var(--bg-tertiary); border-radius: 8px;">
                        <div style="font-size: 24px; font-weight: bold;">${formatNumber(seedResult.median_subs)}</div>
                        <div style="font-size: 12px; color: var(--text-muted);">Median Subs</div>
                    </div>
                    <div style="text-align: center; padding: 12px; background: var(--bg-tertiary); border-radius: 8px;">
                        <div style="font-size: 24px; font-weight: bold; color: ${multiplierColor};">${seedResult.multiplier || 0}x</div>
                        <div style="font-size: 12px; color: var(--text-muted);">Multiplier</div>
                    </div>
                    <div style="text-align: center; padding: 12px; background: var(--bg-tertiary); border-radius: 8px;">
                        <div style="font-size: 24px; font-weight: bold; color: var(--success-color);">${seedResult.opportunity_score}</div>
                        <div style="font-size: 12px; color: var(--text-muted);">Opportunity</div>
                    </div>
                </div>
                <p style="margin-bottom: 8px;"><strong>Difficulty:</strong> <span style="color: ${difficultyColor};">${seedResult.difficulty_level}</span> | <strong>Region:</strong> ${region}</p>
                ${seedResult.top_videos ? `
                    <details style="margin-top: 12px;">
                        <summary style="cursor: pointer; color: var(--accent);">Top Competing Videos</summary>
                        <ul style="margin-top: 8px; padding-left: 20px;">
                            ${seedResult.top_videos.map(v => `
                                <li style="margin-bottom: 6px;">
                                    <a href="https://youtube.com/watch?v=${v.video_id}" target="_blank" style="color: var(--text-primary);">${v.title}</a>
                                    <span style="color: var(--text-muted);"> - ${formatNumber(v.views)} views, ${formatNumber(v.subs)} subs</span>
                                </li>
                            `).join('')}
                        </ul>
                    </details>
                ` : ''}
            `;
            document.getElementById('keyword-seed-result').style.display = 'block';

            // Show suggestions
            if (result.suggestions && result.suggestions.length > 0) {
                const tbody = document.getElementById('keywords-tbody');
                tbody.innerHTML = result.suggestions.map(s => {
                    const color = getDifficultyColor(s.difficulty_level);
                    const multColor = s.multiplier >= 5 ? 'var(--success-color)' : s.multiplier >= 2 ? 'var(--warning-color)' : 'var(--text-muted)';
                    return `
                        <tr style="border-bottom: 1px solid var(--border-color);">
                            <td style="padding: 12px;">${s.keyword}</td>
                            <td style="padding: 12px; text-align: center;">
                                <span style="display: inline-block; padding: 4px 10px; border-radius: 4px; background: ${color}; color: white; font-size: 12px;">
                                    ${s.difficulty_level} (${s.difficulty_score})
                                </span>
                            </td>
                            <td style="padding: 12px; text-align: right;">${formatNumber(s.avg_views)}</td>
                            <td style="padding: 12px; text-align: right;">${formatNumber(s.median_subs)}</td>
                            <td style="padding: 12px; text-align: center;">
                                <span style="font-weight: bold; color: ${multColor};">${s.multiplier || 0}x</span>
                            </td>
                            <td style="padding: 12px; text-align: center;">
                                <span style="font-weight: bold; color: ${s.opportunity_score > 60 ? 'var(--success-color)' : s.opportunity_score > 30 ? 'var(--warning-color)' : 'var(--error)'}">${s.opportunity_score}</span>
                            </td>
                        </tr>
                    `;
                }).join('');
                document.getElementById('keyword-suggestions').style.display = 'block';
            }

            addLog(`Found ${result.suggestions?.length || 0} related keywords`, 'success');
            showToast('Keyword research complete!');
        } else {
            showToast(result.error || 'Research failed', 'error');
            addLog(`Error: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Failed to research keywords', 'error');
        addLog(`Error: ${error.message}`, 'error');
    }

    hideLoading();
}

function getDifficultyColor(level) {
    switch (level) {
        case 'Low': return 'var(--success-color)';
        case 'Medium': return 'var(--warning-color)';
        case 'High': return 'var(--error)';
        default: return 'var(--text-muted)';
    }
}

// Store keyword research results for export
let lastKeywordResults = null;

function exportKeywordsCSV() {
    if (!lastKeywordResults || !lastKeywordResults.suggestions || lastKeywordResults.suggestions.length === 0) {
        showToast('No keywords to export. Run research first.', 'error');
        return;
    }

    // CSV header
    let csv = 'Keyword,Difficulty,Difficulty Score,Avg Views,Median Subs,Multiplier,Opportunity\n';

    // Add seed keyword first
    if (lastKeywordResults.seed_result) {
        const s = lastKeywordResults.seed_result;
        csv += `"${s.keyword}",${s.difficulty_level},${s.difficulty_score},${s.avg_views},${s.median_subs},${s.multiplier || 0},${s.opportunity_score}\n`;
    }

    // Add all suggestions
    lastKeywordResults.suggestions.forEach(s => {
        csv += `"${s.keyword}",${s.difficulty_level},${s.difficulty_score},${s.avg_views},${s.median_subs},${s.multiplier || 0},${s.opportunity_score}\n`;
    });

    // Create and download file
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `keywords_${lastKeywordResults.seed_keyword.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);

    showToast('Keywords exported to CSV!');
    addLog(`Exported ${lastKeywordResults.suggestions.length + 1} keywords to CSV`, 'success');
}

// Saved keywords storage (grouped by seed keyword with metrics)
// Structure: { [seedKeyword]: [{ keyword, difficulty, multiplier, median_subs, opportunity }, ...] }
let savedKeywordGroups = JSON.parse(localStorage.getItem('savedKeywordGroups') || '{}');
let selectedTags = new Set(JSON.parse(localStorage.getItem('selectedTags') || '[]'));

// Migrate old flat format to new grouped format
(function migrateOldKeywords() {
    const oldKeywords = JSON.parse(localStorage.getItem('savedKeywords') || '[]');
    if (oldKeywords.length > 0 && Object.keys(savedKeywordGroups).length === 0) {
        console.log('Migrating old keywords to new grouped format...');
        savedKeywordGroups['Migrated Keywords'] = oldKeywords.map(k => ({
            keyword: k.keyword,
            difficulty: k.difficulty || 'Unknown',
            multiplier: k.multiplier || 0,
            median_subs: k.median_subs || 0,
            opportunity: k.opportunity || 0
        }));
        localStorage.setItem('savedKeywordGroups', JSON.stringify(savedKeywordGroups));
        localStorage.removeItem('savedKeywords'); // Clean up old key
        console.log(`Migrated ${oldKeywords.length} keywords`);
    }
})();

function saveKeywordsToTags() {
    if (!lastKeywordResults || !lastKeywordResults.suggestions) {
        showToast('No keywords to save. Run research first.', 'error');
        return;
    }

    const seedKeyword = lastKeywordResults.seed_keyword;

    // Create group for this seed keyword if doesn't exist
    if (!savedKeywordGroups[seedKeyword]) {
        savedKeywordGroups[seedKeyword] = [];
    }

    const existingKeywords = new Set(savedKeywordGroups[seedKeyword].map(k => k.keyword));
    let addedCount = 0;

    // Add seed keyword result
    if (lastKeywordResults.seed_result) {
        const s = lastKeywordResults.seed_result;
        if (!existingKeywords.has(s.keyword)) {
            savedKeywordGroups[seedKeyword].push({
                keyword: s.keyword,
                difficulty: s.difficulty_level,
                multiplier: s.multiplier || 0,
                median_subs: s.median_subs || 0,
                opportunity: s.opportunity_score
            });
            addedCount++;
        }
    }

    // Add suggestions
    lastKeywordResults.suggestions.forEach(s => {
        if (!existingKeywords.has(s.keyword)) {
            savedKeywordGroups[seedKeyword].push({
                keyword: s.keyword,
                difficulty: s.difficulty_level,
                multiplier: s.multiplier || 0,
                median_subs: s.median_subs || 0,
                opportunity: s.opportunity_score
            });
            addedCount++;
        }
    });

    localStorage.setItem('savedKeywordGroups', JSON.stringify(savedKeywordGroups));

    showToast(`Saved ${addedCount} keywords to "${seedKeyword}" group!`);
    addLog(`Saved ${addedCount} keywords to group: ${seedKeyword}`, 'success');

    renderSavedKeywords();
}

function renderSavedKeywords() {
    const container = document.getElementById('saved-keywords-container');
    if (!container) return;

    const groups = Object.keys(savedKeywordGroups);

    if (groups.length === 0) {
        container.innerHTML = '<span style="color: var(--text-muted);">No saved keywords. Go to Keywords tab and research, then click "Save to Tags".</span>';
        return;
    }

    // Render each group as a collapsible box
    container.innerHTML = groups.map(seedKw => {
        const keywords = savedKeywordGroups[seedKw];
        const selectedCount = keywords.filter(k => selectedTags.has(k.keyword)).length;

        return `
            <div style="margin-bottom: 16px; border: 1px solid var(--border-color); border-radius: 8px; overflow: hidden;">
                <div style="padding: 10px 12px; background: var(--bg-tertiary); display: flex; justify-content: space-between; align-items: center;">
                    <h5 style="margin: 0;">🏷️ ${seedKw} <span style="font-weight: normal; color: var(--text-muted);">(${selectedCount}/${keywords.length} selected)</span></h5>
                    <div style="display: flex; gap: 6px;">
                        <button class="btn-secondary" onclick="selectGroupKeywords('${seedKw.replace(/'/g, "\\'")}')" style="padding: 3px 8px; font-size: 11px;">Select All</button>
                        <button class="btn-secondary" onclick="deselectGroupKeywords('${seedKw.replace(/'/g, "\\'")}')" style="padding: 3px 8px; font-size: 11px;">Deselect</button>
                        <button class="btn-secondary" onclick="deleteKeywordGroup('${seedKw.replace(/'/g, "\\'")}')" style="padding: 3px 8px; font-size: 11px; color: var(--error);">×</button>
                    </div>
                </div>
                <div style="padding: 10px; display: flex; flex-wrap: wrap; gap: 8px;">
                    ${keywords.map((k, i) => {
            const isSelected = selectedTags.has(k.keyword);
            const diffColor = k.difficulty === 'Low' ? 'var(--success-color)' : k.difficulty === 'Medium' ? 'var(--warning-color)' : 'var(--error)';
            const multColor = k.multiplier >= 5 ? 'var(--success-color)' : k.multiplier >= 2 ? 'var(--warning-color)' : 'var(--text-muted)';
            const subsFormatted = formatNumber(k.median_subs || 0);

            return `
                            <div class="saved-keyword-tag ${isSelected ? 'selected' : ''}" 
                                onclick="toggleGroupKeyword('${seedKw.replace(/'/g, "\\'")}', ${i})"
                                style="padding: 6px 10px; border-radius: 6px; cursor: pointer; border: 1px solid ${isSelected ? 'var(--accent)' : 'var(--border-color)'}; background: ${isSelected ? 'rgba(138, 43, 226, 0.2)' : 'var(--bg-primary)'};">
                                <div style="font-weight: 500; font-size: 13px;">${k.keyword}</div>
                                <div style="font-size: 10px; margin-top: 2px; display: flex; gap: 6px; flex-wrap: wrap;">
                                    <span style="color: ${diffColor};">${k.difficulty}</span>
                                    <span style="color: var(--text-muted);">${subsFormatted} subs</span>
                                    <span style="color: ${multColor};">${k.multiplier}x</span>
                                    <span style="color: var(--success-color);">Opp: ${k.opportunity}</span>
                                </div>
                            </div>
                        `;
        }).join('')}
                </div>
            </div>
        `;
    }).join('');
}

function toggleGroupKeyword(seedKw, index) {
    const keyword = savedKeywordGroups[seedKw][index].keyword;
    if (selectedTags.has(keyword)) {
        selectedTags.delete(keyword);
    } else {
        selectedTags.add(keyword);
    }
    localStorage.setItem('selectedTags', JSON.stringify([...selectedTags]));
    renderSavedKeywords();
    updateSelectedTagsDisplay();
}

function selectGroupKeywords(seedKw) {
    savedKeywordGroups[seedKw].forEach(k => selectedTags.add(k.keyword));
    localStorage.setItem('selectedTags', JSON.stringify([...selectedTags]));
    renderSavedKeywords();
    updateSelectedTagsDisplay();
    showToast(`Selected all "${seedKw}" keywords`);
}

function deselectGroupKeywords(seedKw) {
    savedKeywordGroups[seedKw].forEach(k => selectedTags.delete(k.keyword));
    localStorage.setItem('selectedTags', JSON.stringify([...selectedTags]));
    renderSavedKeywords();
    updateSelectedTagsDisplay();
    showToast(`Deselected all "${seedKw}" keywords`);
}

function deleteKeywordGroup(seedKw) {
    if (confirm(`Delete all "${seedKw}" keywords?`)) {
        // Remove from selected tags
        savedKeywordGroups[seedKw].forEach(k => selectedTags.delete(k.keyword));
        // Delete the group
        delete savedKeywordGroups[seedKw];
        localStorage.setItem('savedKeywordGroups', JSON.stringify(savedKeywordGroups));
        localStorage.setItem('selectedTags', JSON.stringify([...selectedTags]));
        renderSavedKeywords();
        updateSelectedTagsDisplay();
        showToast(`Deleted "${seedKw}" keyword group`);
    }
}

function selectAllSavedKeywords() {
    Object.values(savedKeywordGroups).flat().forEach(k => selectedTags.add(k.keyword));
    localStorage.setItem('selectedTags', JSON.stringify([...selectedTags]));
    renderSavedKeywords();
    updateSelectedTagsDisplay();
    const totalCount = Object.values(savedKeywordGroups).flat().length;
    showToast(`Selected all ${totalCount} saved keywords`);
}

function deselectAllSavedKeywords() {
    Object.values(savedKeywordGroups).flat().forEach(k => selectedTags.delete(k.keyword));
    localStorage.setItem('selectedTags', JSON.stringify([...selectedTags]));
    renderSavedKeywords();
    updateSelectedTagsDisplay();
    showToast('Deselected all keywords');
}

function deleteSelectedKeywords() {
    if (selectedTags.size === 0) {
        showToast('No keywords selected to delete', 'error');
        return;
    }

    if (!confirm(`Delete ${selectedTags.size} selected keywords?`)) {
        return;
    }

    // Remove selected keywords from all groups
    for (const seedKw of Object.keys(savedKeywordGroups)) {
        savedKeywordGroups[seedKw] = savedKeywordGroups[seedKw].filter(k => !selectedTags.has(k.keyword));
        // Remove empty groups
        if (savedKeywordGroups[seedKw].length === 0) {
            delete savedKeywordGroups[seedKw];
        }
    }

    // Clear selections
    selectedTags = new Set();

    localStorage.setItem('savedKeywordGroups', JSON.stringify(savedKeywordGroups));
    localStorage.setItem('selectedTags', JSON.stringify([...selectedTags]));
    renderSavedKeywords();
    updateSelectedTagsDisplay();
    showToast('Deleted selected keywords');
}

function clearSavedKeywords() {
    if (confirm('Clear ALL saved keyword groups?')) {
        savedKeywordGroups = {};
        selectedTags = new Set();
        localStorage.setItem('savedKeywordGroups', JSON.stringify(savedKeywordGroups));
        localStorage.setItem('selectedTags', JSON.stringify([...selectedTags]));
        renderSavedKeywords();
        updateSelectedTagsDisplay();
        showToast('All saved keywords cleared');
    }
}

function selectAllVideoTags() {
    const tags = document.querySelectorAll('#info-tags-container .tag');
    tags.forEach(tag => {
        if (!tag.classList.contains('selected')) {
            tag.click();
        }
    });
    showToast('Selected all video tags');
}

function updateSelectedTagsDisplay() {
    try {
        console.log('[updateSelectedTagsDisplay] START');

        var container = document.getElementById('all-selected-tags');
        var charCountEl = document.getElementById('tags-char-count');

        if (!container) {
            console.log('[updateSelectedTagsDisplay] ERROR: Container not found');
            return;
        }

        // Convert selectedTags Set to array
        var tagsArray = [];
        selectedTags.forEach(function (tag) {
            tagsArray.push(tag);
        });

        console.log('[updateSelectedTagsDisplay] tagsArray length:', tagsArray.length);

        if (tagsArray.length === 0) {
            container.innerHTML = '<span style="color: var(--text-muted);">No tags selected yet</span>';
            if (charCountEl) charCountEl.textContent = '0 / 500 chars';
            return;
        }

        // Calculate character count
        var tagsString = tagsArray.join(',');
        var charCount = tagsString.length;

        console.log('[updateSelectedTagsDisplay] charCount:', charCount);

        if (charCountEl) {
            charCountEl.textContent = charCount + ' / 500 chars';
            if (charCount > 500) {
                charCountEl.style.color = 'var(--error)';
            } else if (charCount > 400) {
                charCountEl.style.color = 'var(--warning-color)';
            } else {
                charCountEl.style.color = 'var(--text-primary)';
            }
        }

        // Build HTML
        var htmlParts = [];
        for (var i = 0; i < tagsArray.length; i++) {
            var tag = tagsArray[i];
            var escapedTag = tag.replace(/'/g, "\\'");
            htmlParts.push('<span style="padding: 4px 10px; background: var(--accent); color: white; border-radius: 4px; font-size: 12px; cursor: pointer; display: inline-block; margin: 2px;" onclick="removeSelectedTag(\'' + escapedTag + '\')">' + tag + ' ×</span>');
        }

        container.innerHTML = htmlParts.join('');
        console.log('[updateSelectedTagsDisplay] DONE, rendered', tagsArray.length, 'tags');

    } catch (err) {
        console.error('[updateSelectedTagsDisplay] CAUGHT ERROR:', err);
    }
}

function removeSelectedTag(tag) {
    selectedTags.delete(tag);
    localStorage.setItem('selectedTags', JSON.stringify([...selectedTags]));
    renderSavedKeywords();
    updateSelectedTagsDisplay();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function () {
    setTimeout(() => {
        renderSavedKeywords();
        updateSelectedTagsDisplay();
    }, 500);
});

async function generateTitleOptions() {
    let topic = document.getElementById('title-topic').value.trim();
    const channelType = document.getElementById('title-channel-type').value;
    const outline = document.getElementById('title-outline').value.trim();

    // Use selected inspiration title as fallback topic
    if (!topic && selectedInspirationTitle) {
        topic = selectedInspirationTitle;
        addLog(`Using inspiration title as topic: ${topic}`, 'info');
    }

    if (!topic) {
        showToast('Please enter a topic or select an inspiration title', 'error');
        return;
    }

    if (!selectedInspirationTitle) {
        showToast('Please select an inspiration title', 'error');
        return;
    }

    showLoading('Generating title options...');
    addLog('Generating CTR-optimized titles...', 'info');

    try {
        const response = await fetch('/api/generate-titles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                topic: topic,
                outline: outline,
                inspiration_title: selectedInspirationTitle,
                channel_type: channelType
            })
        });

        const result = await response.json();

        if (result.success && result.titles) {
            renderGeneratedTitles(result.titles);
            document.getElementById('generated-titles-section').style.display = 'block';
            showToast('Titles generated!');
            addLog(`Generated ${result.titles.length} title options`, 'success');
        } else {
            showToast(result.error || 'Failed to generate titles', 'error');
        }
    } catch (error) {
        showToast('Failed to generate titles', 'error');
        addLog(`Error: ${error.message}`, 'error');
    }

    hideLoading();
}

function renderGeneratedTitles(titles) {
    const container = document.getElementById('generated-titles-list');
    container.innerHTML = titles.map((title, i) => `
        <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: var(--bg-tertiary); border-radius: 8px; margin-bottom: 10px;">
            <span style="font-size: 20px; font-weight: bold; color: var(--primary-color);">${i + 1}</span>
            <span style="flex: 1; font-size: 15px;">${title}</span>
            <button class="btn-secondary" onclick="copyTitle('${title.replace(/'/g, "\\'")}')">📋 Copy</button>
            <button class="btn-primary" onclick="useTitle('${title.replace(/'/g, "\\'")}')">Use This</button>
        </div>
    `).join('');
}

function copyTitle(title) {
    navigator.clipboard.writeText(title);
    showToast('Title copied to clipboard!');
}

function useTitle(title) {
    // Finalize the title
    fetch('/api/finalize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'title', value: title })
    }).then(r => r.json()).then(result => {
        if (result.success) {
            showToast(`✅ Title finalized: "${title.substring(0, 40)}..."`);
        }
    });
}

// ============== MORE INFO TAB ==============

let selectedInfoVideoId = null;
let allSelectedTags = new Set();

async function loadVideosForInfo() {
    showLoading('Loading saved videos...');

    try {
        const response = await fetch('/api/get-saved-videos');
        const result = await response.json();

        if (result.success) {
            cachedSavedVideos = result.videos;
            renderInfoVideoGrid(result.videos);
            showToast(`Loaded ${result.videos.length} videos`);
        } else {
            showToast(result.error || 'Failed to load videos', 'error');
        }
    } catch (error) {
        showToast('Failed to load videos', 'error');
    }

    hideLoading();
}

function renderInfoVideoGrid(videos) {
    const grid = document.getElementById('info-videos-grid');

    if (!videos || videos.length === 0) {
        grid.innerHTML = '<div class="empty-state"><span class="empty-icon">📋</span><p>No saved videos</p></div>';
        return;
    }

    grid.innerHTML = videos.map(video => `
        <div class="video-card" onclick="selectVideoForInfo('${video.video_id}')" 
             style="cursor: pointer; border: 2px solid transparent; border-radius: 8px; overflow: hidden; transition: border-color 0.2s;"
             id="info-card-${video.video_id}">
            <img src="${video.thumbnail}" style="width: 100%; aspect-ratio: 16/9; object-fit: cover;">
            <p style="padding: 8px; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${video.title}</p>
        </div>
    `).join('');
}

async function selectVideoForInfo(videoId) {
    // Highlight selected
    document.querySelectorAll('#info-videos-grid .video-card').forEach(card => {
        card.style.borderColor = 'transparent';
    });
    document.getElementById(`info-card-${videoId}`).style.borderColor = 'var(--accent-color)';

    selectedInfoVideoId = videoId;

    showLoading('Fetching video details from YouTube API...');

    try {
        const response = await fetch(`/api/video-info/${videoId}`);
        const result = await response.json();

        if (result.success) {
            displayVideoDetails(result);
        } else {
            showToast(result.error || 'Failed to fetch details', 'error');
        }
    } catch (error) {
        showToast('Failed to fetch video details', 'error');
    }

    hideLoading();
}

function displayVideoDetails(data) {
    document.getElementById('video-details-panel').style.display = 'block';
    document.getElementById('info-video-title').textContent = data.title;
    document.getElementById('info-view-count').textContent = formatNumber(data.viewCount);
    document.getElementById('info-duration').textContent = data.duration_formatted || data.duration;
    document.getElementById('info-description').value = data.description || '';

    // Render tags
    const tagsContainer = document.getElementById('info-tags-container');
    const tags = data.tags || [];

    tagsContainer.innerHTML = tags.map(tag => `
        <span class="tag-chip" onclick="toggleTag(this, '${tag.replace(/'/g, "\\'")}')"
              style="padding: 6px 12px; background: var(--bg-tertiary); border-radius: 16px; cursor: pointer; font-size: 12px; transition: all 0.2s; border: 2px solid transparent;"
              ${allSelectedTags.has(tag) ? 'data-selected="true" style="background: var(--accent-color); color: white; border-color: var(--accent-color);"' : ''}>
            ${tag}
        </span>
    `).join('');

    // Scroll to panel
    document.getElementById('video-details-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function toggleTag(element, tag) {
    if (allSelectedTags.has(tag)) {
        allSelectedTags.delete(tag);
        selectedTags.delete(tag);  // Also remove from selectedTags
        element.style.background = 'var(--bg-tertiary)';
        element.style.color = '';
        element.style.borderColor = 'transparent';
    } else {
        allSelectedTags.add(tag);
        selectedTags.add(tag);  // Also add to selectedTags
        element.style.background = 'var(--accent-color)';
        element.style.color = 'white';
        element.style.borderColor = 'var(--accent-color)';
    }
    localStorage.setItem('selectedTags', JSON.stringify([...selectedTags]));
    updateSelectedTagsDisplay();
}

// NOTE: updateSelectedTagsDisplay is defined earlier (around line 3484) and uses selectedTags Set
// The old allSelectedTags-based version was removed as it was a duplicate

async function rewriteDescription() {
    const description = document.getElementById('info-description').value;
    if (!description) {
        showToast('No description to rewrite', 'error');
        return;
    }

    showLoading('Rewriting description with AI...');

    try {
        const response = await fetch('/api/rewrite-description', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description })
        });
        const result = await response.json();

        if (result.success) {
            document.getElementById('info-description').value = result.rewritten;
            showToast('Description rewritten!');
        } else {
            showToast(result.error || 'Failed to rewrite', 'error');
        }
    } catch (error) {
        showToast('Failed to rewrite description', 'error');
    }

    hideLoading();
}

async function finalizeDescription() {
    const description = document.getElementById('info-description').value;

    const response = await fetch('/api/finalize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'description', value: description })
    });
    const result = await response.json();

    if (result.success) {
        showToast('✅ Description saved for posting!');
    }
}

async function finalizeTags() {
    const tags = Array.from(allSelectedTags);

    if (tags.length === 0) {
        showToast('No tags selected', 'error');
        return;
    }

    const response = await fetch('/api/finalize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'tags', value: tags })
    });
    const result = await response.json();

    if (result.success) {
        showToast(`✅ ${tags.length} tags saved for posting!`);
    }
}

function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

// ============== POST TO YOUTUBE TAB ==============

async function refreshFinalizedItems() {
    try {
        const response = await fetch('/api/finalized');
        const result = await response.json();

        if (result.success) {
            const finalized = result.finalized;

            // Update thumbnail status
            if (finalized.thumbnail) {
                document.getElementById('finalized-thumbnail-status').textContent = '✅';
                document.getElementById('finalized-thumbnail-text').textContent = 'Ready';
                document.getElementById('finalized-thumbnail-preview').src = finalized.thumbnail;
                document.getElementById('finalized-thumbnail-preview').style.display = 'block';
            }

            // Update title status
            if (finalized.title) {
                document.getElementById('finalized-title-status').textContent = '✅';
                document.getElementById('finalized-title-text').textContent = finalized.title.substring(0, 50) + '...';
            }

            // Update description status
            if (finalized.description) {
                document.getElementById('finalized-description-status').textContent = '✅';
                document.getElementById('finalized-description-text').textContent = finalized.description.substring(0, 80) + '...';
            }

            // Update tags status
            if (finalized.tags && finalized.tags.length > 0) {
                document.getElementById('finalized-tags-status').textContent = '✅';
                document.getElementById('finalized-tags-text').textContent = `${finalized.tags.length} tags selected`;
            }

            showToast('Status refreshed');
        }
    } catch (error) {
        showToast('Failed to refresh status', 'error');
    }
}
// ========== CUSTOM THUMBNAIL FUNCTIONS ==========

let selectedCustomThumbnailPath = null;

async function loadCustomThumbnails() {
    try {
        const response = await fetch('/api/custom-thumbnails');
        const result = await response.json();

        const grid = document.getElementById('custom-thumbnails-grid');

        if (result.success && result.thumbnails.length > 0) {
            grid.innerHTML = result.thumbnails.map((thumb, i) => `
                <div onclick="selectCustomThumbnail('${thumb.path}', '${thumb.name}')" 
                     style="cursor: pointer; border: 2px solid transparent; border-radius: 8px; overflow: hidden; transition: all 0.2s;"
                     class="thumbnail-option" id="thumb-${i}">
                    <img src="${thumb.path}" style="width: 100%; aspect-ratio: 16/9; object-fit: cover;">
                    <div style="padding: 6px; font-size: 11px; color: var(--text-muted); text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        ${thumb.name}
                    </div>
                </div>
            `).join('');
            showToast(`Found ${result.thumbnails.length} custom thumbnails`);
        } else {
            grid.innerHTML = `<p style="color: var(--text-muted);">No thumbnails found. Add images to <code>${result.folder}</code></p>`;
        }
    } catch (error) {
        showToast('Failed to load custom thumbnails', 'error');
    }
}

function selectCustomThumbnail(path, name) {
    selectedCustomThumbnailPath = path;

    // Update visual selection
    document.querySelectorAll('.thumbnail-option').forEach(el => {
        el.style.border = '2px solid transparent';
    });
    event.currentTarget.style.border = '2px solid var(--primary-color)';

    // Show selection
    document.getElementById('selected-custom-thumbnail').style.display = 'block';
    document.getElementById('selected-thumbnail-name').textContent = name;
}

async function useCustomThumbnail() {
    if (!selectedCustomThumbnailPath) {
        showToast('Please select a thumbnail first', 'error');
        return;
    }

    // Store as finalized thumbnail locally
    window.finalizedContent = window.finalizedContent || {};
    window.finalizedContent.thumbnail = {
        url: selectedCustomThumbnailPath,
        isCustom: true
    };

    // CRITICAL: Send to backend to persist in app_state
    try {
        const response = await fetch('/api/finalize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: 'thumbnail',
                value: window.finalizedContent.thumbnail
            })
        });

        const result = await response.json();
        if (!result.success) {
            showToast('Failed to save thumbnail selection', 'error');
            return;
        }
    } catch (error) {
        console.error('Failed to finalize thumbnail:', error);
        showToast('Failed to save thumbnail selection', 'error');
        return;
    }

    showToast('✅ Custom thumbnail selected for upload!');

    // Update the preview in posting tab
    const preview = document.getElementById('finalized-thumbnail-preview');
    if (preview) {
        preview.src = selectedCustomThumbnailPath;
        preview.style.display = 'block';
    }
    document.getElementById('finalized-thumbnail-status').textContent = '✅';
    document.getElementById('finalized-thumbnail-text').textContent = 'Custom thumbnail selected';
}

// ========== FINAL VIDEO FUNCTIONS ==========

let selectedVideoPath = null;

async function loadFinalVideos() {
    try {
        const response = await fetch('/api/final-videos');
        const result = await response.json();

        const list = document.getElementById('final-videos-list');

        if (result.success && result.videos.length > 0) {
            list.innerHTML = result.videos.map((video, i) => `
                <div onclick="selectVideoForUpload('${video.path}', '${video.name}')" 
                     style="cursor: pointer; padding: 12px; margin-bottom: 8px; background: var(--bg-tertiary); border-radius: 8px; border: 2px solid transparent; transition: all 0.2s; display: flex; justify-content: space-between; align-items: center;"
                     class="video-option" id="video-${i}">
                    <span>🎬 ${video.name}</span>
                    <span style="color: var(--text-muted); font-size: 12px;">${video.size_mb} MB</span>
                </div>
            `).join('');
            showToast(`Found ${result.videos.length} videos`);
        } else {
            list.innerHTML = `<p style="color: var(--text-muted);">No videos found. Generate a video first or add videos to <code>${result.folder}</code></p>`;
        }
    } catch (error) {
        showToast('Failed to load videos', 'error');
    }
}

function selectVideoForUpload(path, name) {
    selectedVideoPath = path;

    // Update visual selection
    document.querySelectorAll('.video-option').forEach(el => {
        el.style.border = '2px solid transparent';
        el.style.background = 'var(--bg-tertiary)';
    });
    event.currentTarget.style.border = '2px solid var(--success)';
    event.currentTarget.style.background = 'var(--bg-secondary)';

    // Show selection info
    document.getElementById('selected-video-info').style.display = 'block';
    document.getElementById('selected-video-name').textContent = name;

    // Store for upload
    window.selectedVideoForUpload = path;

    showToast(`Selected: ${name}`);
}


async function uploadToYouTube() {
    // Check auth first
    const authCheck = await fetch('/api/youtube/auth-status');
    const authResult = await authCheck.json();

    if (!authResult.authenticated) {
        showToast('Please connect your YouTube account first', 'error');
        return;
    }

    const privacy = document.getElementById('upload-privacy').value;

    showLoading('Uploading video to YouTube... This may take a few minutes.');
    addLog('Starting YouTube upload...', 'info');

    try {
        const response = await fetch('/api/youtube/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                privacy,
                video_path: window.selectedVideoForUpload || null
            })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`🎉 Video uploaded! ${result.video_url}`, 'success');
            addLog(`Upload complete! Video ID: ${result.video_id}`, 'success');

            // Show success with link
            alert(`Video uploaded successfully!\n\nURL: ${result.video_url}\n\nIt may take a few minutes to process.`);
        } else {
            showToast(result.error || 'Upload failed', 'error');
            addLog(`Upload error: ${result.error}`, 'error');
        }
    } catch (error) {
        showToast('Upload failed: ' + error.message, 'error');
        addLog(`Error: ${error.message}`, 'error');
    }

    hideLoading();
}

async function checkYouTubeAuth() {
    try {
        const response = await fetch('/api/youtube/auth-status');
        const result = await response.json();

        const icon = document.getElementById('auth-status-icon');
        const text = document.getElementById('auth-status-text');

        if (result.authenticated) {
            icon.textContent = '✅';
            text.textContent = 'YouTube account connected';
            text.style.color = 'var(--success-color)';
        } else {
            icon.textContent = '❌';
            text.textContent = 'Not connected - click "Connect YouTube Account"';
            text.style.color = 'var(--error-color)';
        }

        // Also check dependencies
        if (!result.dependencies?.google_api_available) {
            text.textContent = 'Missing: pip install google-auth-oauthlib google-api-python-client';
        }
    } catch (error) {
        document.getElementById('auth-status-text').textContent = 'Error checking status';
    }
}

// Check auth on page load for Post tab
document.addEventListener('DOMContentLoaded', () => {
    // Check if returning from OAuth
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('auth') === 'success') {
        showToast('✅ YouTube account connected successfully!', 'success');
        // Switch to Post tab
        document.querySelector('[data-step="11"]')?.click();
    }
});

// Finalize thumbnail from Thumbnail tab
async function finalizeThumbnail() {
    const imgSrc = document.getElementById('generated-thumbnail-img').src;
    if (!imgSrc) {
        showToast('Generate a thumbnail first', 'error');
        return;
    }

    const response = await fetch('/api/finalize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'thumbnail', value: imgSrc })
    });
    const result = await response.json();

    if (result.success) {
        showToast('✅ Thumbnail finalized for posting!');
    }
}

// ==========================================
// LOCKED TEMPLATE GENERATOR (V5)
// ==========================================
async function generateLockedThumbnail() {
    const topicInput = document.getElementById('locked-topic-input');
    const resultDiv = document.getElementById('locked-result');
    const imgElement = document.getElementById('locked-img');
    const btn = document.querySelector('button[onclick="generateLockedThumbnail()"]');

    const topic = topicInput.value.trim();
    if (!topic) {
        alert("Please enter a topic first.");
        return;
    }

    // UI Loading State
    btn.disabled = true;
    btn.innerHTML = "⏳ Generating...";
    resultDiv.style.display = 'none';

    try {
        const response = await fetch('/api/generate-thumbnail-locked', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic: topic })
        });

        const data = await response.json();

        if (data.success) {
            imgElement.src = `${data.image_url}?t=${new Date().getTime()}`;
            resultDiv.style.display = 'block';
        } else {
            alert("Error: " + data.message);
        }

    } catch (e) {
        alert("Request Failed: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = "Generate V5";
    }
}
