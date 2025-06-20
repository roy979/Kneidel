// ───────────────────────── Config ─────────────────────────
const API_BASE = 'https://kneidel.onrender.com';
const GITHUB_API_BASE = 'https://api.github.com/repos/roy979/Kneidel/contents/Packages';
let token, headers = {};

let audioContext = new AudioContext();
let bufferCache = {};
let stems = [];
let remoteSongs = [];
let currentIndex = 0;
let stage = 0;
let isPlaying = false;
let audioSource, gainNodes = [];

// ───────────────────────── On Load ────────────────────────
(async function init() {
  try {
    const res = await fetch(`${API_BASE}/api/token`);
    const { token: t, spotid, spotsec } = await res.json();
    token = t;
    headers = { Authorization: `token ${token}` };
  } catch (e) {
    console.warn('Failed to fetch token', e);
  }
})();

// ───────────────────────── UI Bindings ───────────────────
document.getElementById('selectPackagesBtn').onclick = selectPackages;
document.getElementById('playPauseBtn').onclick = togglePlay;
document.getElementById('skipBtn').onclick = skipStage;
document.getElementById('rewindBtn').onclick = rewind;
document.getElementById('guessBtn').onclick = checkGuess;


function log(text, color='black') {
  const fb = document.getElementById('feedback');
  fb.textContent = text;
  fb.style.color = color;
}

// ───────────────────────── Package Flow ───────────────────
async function selectPackages() {
  log('Loading list of packages…', 'blue');
  const pkgList = await (await fetch(GITHUB_API_BASE, { headers })).json();
  const packages = pkgList.filter(i => i.type === 'dir').map(i => i.name);
  const sel = prompt('Select packages (comma-separated):\n'+packages.join('\n'));
  if (!sel) return;
  const chosen = sel.split(',').map(s => s.trim());
  
  remoteSongs = [];
  for (const pkg of chosen) {
    const url = `${GITHUB_API_BASE}/${pkg}/htdemucs_6s`;
    const res = await fetch(url, { headers });
    const entries = await res.json();
    remoteSongs.push(...entries.filter(e => e.type === 'dir').map(e=>`${pkg}/htdemucs_6s/${e.name}`));
  }
  
  if (!remoteSongs.length) return log('No songs found!', 'red');
  log('Preloading first song…', 'green');
  currentIndex = 0;
  stems = [];
  await preloadSong(0);
  loadCurrent();
  setTimeout(() => {
    if (remoteSongs.length > 1) preloadSong(1);
  }, 50);
}

// ───────────────────────── Preload & Load ───────────────
async function preloadSong(idx) {
  const remote = remoteSongs[idx].split('/').slice(2).join('/');
  const api = `${GITHUB_API_BASE}/${remoteSongs[idx]}`;
  const res = await fetch(api, { headers });
  const files = await res.json();
  
  const folder = `song_${idx}`;
  const bufArr = await Promise.all(files
    .filter(f=>f.name.endsWith('.flac'))
    .map(f=>fetch(f.download_url).then(r=>r.arrayBuffer()).then(audioContext.decodeAudioData))
  );
  bufferCache[idx] = bufArr;
}

async function loadCurrent() {
  stems = bufferCache[currentIndex] || [];
  stage = 0;
  renderBars();
}

// ───────────────────────── UI Render ─────────────────────
function renderBars() {
  const container = document.getElementById('bars');
  container.innerHTML = '';
  stems.forEach((_, i) => {
    const bar = document.createElement('div');
    bar.style.width = '0%';
    bar.dataset.idx = i;
    bar.onclick = (e) => {
      stage = parseInt(e.target.dataset.idx);
      renderBars();
    };
    if (i === stage) bar.classList.add('highlight');
    container.append(bar);
  });
}

// ───────────────────────── Playback ──────────────────────
function mixAndPlay() {
  if (!stems.length) return;
  const mix = stems.reduce((sum, buf, i) => {
    const src = audioContext.createBufferSource();
    src.buffer = buf;
    const gain = audioContext.createGain();
    gain.gain.value = i <= stage ? 1 : 0;
    src.connect(gain).connect(audioContext.destination);
    src.start();
    gainNodes.push({src, gain});
    return src;
  }, null);
}

function stopAll() {
  gainNodes.forEach(n => n.src.stop());
  gainNodes = [];
}

// ───────────────────────── Controls ──────────────────────
function togglePlay() {
  if (!stems.length) return log('Load a song first', 'red');
  if (isPlaying) {
    stopAll();
    isPlaying = false;
    return;
  }
  isPlaying = true;
  mixAndPlay();
}

function skipStage() {
  if (stage < stems.length - 1) {
    stage++;
    renderBars();
    if (isPlaying) { stopAll(); mixAndPlay(); }
  } else {
    log(remoteSongs[currentIndex].split('/').pop(), 'green');
    document.getElementById('next-btn')?.click();
  }
}

function rewind() {
  if (isPlaying) {
    isPlaying = false;
    stopAll();
    togglePlay();
  }
}

// ───────────────────────── Guessing Logic ───────────────
function checkGuess() {
  const guess = document.getElementById('searchInput').value.split('-')[0].trim().toLowerCase();
  const answer = remoteSongs[currentIndex].split('/').pop().toLowerCase();
  if (!guess) return;
  if (answer.includes(guess)) {
    log('Correct! 🎉', 'green');
    nextSong();
  } else {
    log('Incorrect, try again!', 'red');
  }
}

// ───────────────────────── Next Song ────────────────────
async function nextSong() {
  stopAll();
  currentIndex++;
  if (currentIndex >= remoteSongs.length) return log('All done!', 'blue');
  
  log('Loading next song…', 'blue');
  if (!bufferCache[currentIndex]) await preloadSong(currentIndex);
  if (currentIndex + 1 < remoteSongs.length && !bufferCache[currentIndex+1]) preloadSong(currentIndex+1);
  loadCurrent();
  log('', '');
}