// State
var videos = [];         // [{video_id, title, is_short, liked_at, display_order, ...}]
var draggedCard = null;
var lazyLoadObserver = null;
var mainGrid = null;

// ── Bootstrap ──────────────────────────────────────────────────────────────

async function init() {
    mainGrid = document.getElementById('videoGrid');

    try {
        var resp = await fetch('/auth/me', { credentials: 'include' });
        if (!resp.ok) { showLogin(); return; }
        showApp();
        await loadAndSync();
    } catch (e) {
        showLogin();
    }
}

function showLogin() {
    document.getElementById('auth-section').style.display = 'block';
    document.getElementById('app-section').style.display  = 'none';
}

function showApp() {
    document.getElementById('auth-section').style.display = 'none';
    document.getElementById('app-section').style.display  = 'block';

    document.getElementById('logoutBtn').addEventListener('click', async function() {
        await fetch('/auth/logout', { credentials: 'include' });
        window.location.reload();
    });

    document.getElementById('copyAll').addEventListener('click', handleCopyAll);

    initializeLazyLoader();
}

async function loadAndSync() {
    await loadShorts();
    syncShorts();  // fire-and-forget background sync
}

// ── Data ───────────────────────────────────────────────────────────────────

async function loadShorts() {
    try {
        var resp = await fetch('/api/shorts', { credentials: 'include' });
        if (!resp.ok) return;
        videos = await resp.json();
        buildGrid();
    } catch (e) {
        console.error('loadShorts failed:', e);
    }
}

async function syncShorts() {
    setSyncStatus('동기화 중...');
    try {
        var resp = await fetch('/api/shorts/sync', { credentials: 'include' });
        if (!resp.ok) { setSyncStatus('동기화 실패'); return; }
        var data = await resp.json();
        if (data.added > 0) {
            setSyncStatus(data.added + '개 새로 추가됨 (총 ' + data.total + '개)');
            await loadShorts();
        } else {
            setSyncStatus('총 ' + data.total + '개' + (data.cached ? ' (캐시)' : ''));
        }
    } catch (e) {
        console.error('syncShorts failed:', e);
        setSyncStatus('동기화 실패');
    }
}

function setSyncStatus(msg) {
    var el = document.getElementById('sync-status');
    if (el) el.textContent = msg;
}

// ── Rendering ──────────────────────────────────────────────────────────────

function buildGrid() {
    if (!mainGrid) return;

    var container = mainGrid.querySelector('.category-grid');
    if (!container) {
        container = document.createElement('div');
        container.className = 'category-grid';
        container.addEventListener('dragover',  handleDragOver);
        container.addEventListener('dragenter', handleDragEnter);
        container.addEventListener('dragleave', handleDragLeave);
        container.addEventListener('drop',      handleDrop);
        mainGrid.innerHTML = '';
        mainGrid.appendChild(container);
    } else {
        container.innerHTML = '';
    }

    if (!videos || videos.length === 0) {
        mainGrid.innerHTML = '<p>동기화 중이거나 좋아요 누른 Shorts가 없습니다.</p>';
        return;
    }

    videos.forEach(function(video) {
        var card = createCardElement(video);
        container.appendChild(card);
        if (lazyLoadObserver) {
            var thumb = card.querySelector('.thumb-container');
            if (thumb) lazyLoadObserver.observe(thumb);
        }
    });
}

function createCardElement(video) {
    var card = document.createElement('div');
    card.className = 'card';
    card.setAttribute('draggable', 'true');
    card.dataset.videoId = video.video_id;

    card.addEventListener('dragstart', handleDragStart);
    card.addEventListener('dragend',   handleDragEnd);

    var thumbUrl = getValidThumbnailUrl(video.video_id);
    var videoUrl = getSmartYouTubeLink(video.video_id, video.is_short);
    var containerClass = video.is_short ? 'thumb-container short-container' : 'thumb-container';

    card.innerHTML =
        '<a href="' + videoUrl + '" target="_blank" rel="noopener noreferrer"' +
           ' class="' + containerClass + '"' +
           ' data-src="' + thumbUrl + '">' +
        '</a>' +
        '<button class="delete-button"' +
            ' onclick="deleteVideoItem(event, \'' + video.video_id + '\')">' +
            '&times;' +
        '</button>';

    return card;
}

// ── Thumbnails ─────────────────────────────────────────────────────────────

function getValidThumbnailUrl(videoId) {
    // Return maxres URL; lazy loader will fall back to hqdefault on error
    return 'https://img.youtube.com/vi/' + videoId + '/maxresdefault.jpg';
}

function getSmartYouTubeLink(videoId, isShort) {
    var ua = navigator.userAgent.toLowerCase();
    var isMobile = /iphone|ipad|ipod|android/i.test(ua);
    if (isMobile)  return 'https://youtu.be/' + videoId;
    if (isShort)   return 'https://youtube.com/shorts/' + videoId;
    return 'https://youtube.com/watch?v=' + videoId;
}

// ── Lazy Loading ───────────────────────────────────────────────────────────

function initializeLazyLoader() {
    lazyLoadObserver = new IntersectionObserver(function(entries, observer) {
        entries.forEach(function(entry) {
            if (!entry.isIntersecting) return;
            var container = entry.target;
            var src = container.getAttribute('data-src');
            if (!src) return;

            // Try maxres; fall back to hqdefault if broken (120×90 grey placeholder)
            var img = new Image();
            img.src = src;
            img.onload = function() {
                var url = this.naturalWidth <= 480
                    ? 'https://img.youtube.com/vi/' + _videoIdFromThumbUrl(src) + '/hqdefault.jpg'
                    : src;
                container.style.backgroundImage = "url('" + url + "')";
            };
            img.onerror = function() {
                var hq = 'https://img.youtube.com/vi/' + _videoIdFromThumbUrl(src) + '/hqdefault.jpg';
                container.style.backgroundImage = "url('" + hq + "')";
            };
            observer.unobserve(container);
        });
    }, { root: null, rootMargin: '200px', threshold: 0 });
}

function _videoIdFromThumbUrl(url) {
    var m = url.match(/\/vi\/([^/]+)\//);
    return m ? m[1] : '';
}

// ── Delete ─────────────────────────────────────────────────────────────────

async function deleteVideoItem(event, videoId) {
    event.preventDefault();
    event.stopPropagation();

    if (!confirm('이 Shorts를 목록에서 삭제할까요?')) return;

    try {
        var resp = await fetch('/api/shorts/' + videoId, {
            method: 'DELETE',
            credentials: 'include',
        });
        if (!resp.ok) { alert('삭제 실패'); return; }

        videos = videos.filter(function(v) { return v.video_id !== videoId; });

        var card = mainGrid.querySelector('.card[data-video-id="' + videoId + '"]');
        if (card) card.remove();
    } catch (e) {
        console.error('deleteVideoItem failed:', e);
        alert('삭제 중 오류가 발생했습니다.');
    }
}

// ── Copy All ───────────────────────────────────────────────────────────────

async function handleCopyAll() {
    if (!videos || videos.length === 0) { alert('복사할 항목이 없습니다.'); return; }

    var links = videos.map(function(v) {
        return 'https://youtube.com/shorts/' + v.video_id;
    }).join('\n');

    try {
        await navigator.clipboard.writeText(links);
        alert('전체 링크가 복사되었습니다.');
    } catch (e) {
        prompt('복사할 링크 목록 (Ctrl+C):', links);
    }
}

// ── Drag & Drop ────────────────────────────────────────────────────────────

function handleDragStart(e) {
    draggedCard = e.target;
    setTimeout(function() {
        if (e.target && e.target.classList) e.target.classList.add('dragging');
    }, 0);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', draggedCard.dataset.videoId);
}

function handleDragEnd(e) {
    if (e.target && e.target.classList) e.target.classList.remove('dragging');
    draggedCard = null;
    document.querySelectorAll('.category-grid.drag-over').forEach(function(g) {
        g.classList.remove('drag-over');
    });
}

function handleDragOver(e) {
    e.preventDefault();
    var grid = e.currentTarget;
    var closest = getClosestCard(grid, e.clientX, e.clientY);
    if (draggedCard) {
        if (closest) grid.insertBefore(draggedCard, closest);
        else          grid.appendChild(draggedCard);
    }
}

function handleDragEnter(e) {
    e.preventDefault();
    if (e.currentTarget && e.currentTarget.classList) e.currentTarget.classList.add('drag-over');
}

function handleDragLeave(e) {
    if (e.currentTarget && e.currentTarget.classList) e.currentTarget.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    var grid = e.currentTarget;
    if (grid && grid.classList) grid.classList.remove('drag-over');
    if (!draggedCard) return;

    var newOrder = Array.from(grid.querySelectorAll('.card')).map(function(c) {
        return c.dataset.videoId;
    });
    videos = newOrder.map(function(id) {
        return videos.find(function(v) { return v.video_id === id; }) || { video_id: id };
    });

    saveOrder(newOrder);
}

function getClosestCard(container, x, y) {
    var cards = Array.from(container.querySelectorAll('.card:not(.dragging)'));
    return cards.reduce(function(closest, child) {
        var box  = child.getBoundingClientRect();
        var dx   = x - (box.left + box.width  / 2);
        var dy   = y - (box.top  + box.height / 2);
        var dist = Math.sqrt(dx * dx + dy * dy);
        return dist < closest.distance ? { distance: dist, element: child } : closest;
    }, { distance: Infinity }).element;
}

async function saveOrder(videoIds) {
    try {
        await fetch('/api/shorts/reorder', {
            method: 'PATCH',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_ids: videoIds }),
        });
    } catch (e) {
        console.error('saveOrder failed:', e);
    }
}

// ── Entry point ────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
