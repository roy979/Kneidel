// Kneidel Game Logic
class KneidelGame {
    constructor() {
        this.sessionId = 'game_' + Date.now();
        this.currentStage = 0;
        this.totalStages = 6;
        this.isPlaying = false;
        this.currentSong = null;
        this.audioManager = new AudioManager();
        this.suggestions = [];
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadPackages();
        this.showPackageModal();
    }

    bindEvents() {
        // Package selection
        document.getElementById('start-game-btn').addEventListener('click', () => this.startGame());
        
        // Game controls
        document.getElementById('play-pause-btn').addEventListener('click', () => this.togglePlayPause());
        document.getElementById('skip-stage-btn').addEventListener('click', () => this.skipStage());
        document.getElementById('rewind-btn').addEventListener('click', () => this.rewind());
        
        // Guess functionality
        document.getElementById('guess-btn').addEventListener('click', () => this.submitGuess());
        document.getElementById('guess-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.submitGuess();
        });
        document.getElementById('guess-input').addEventListener('input', () => this.handleSearchInput());
        
        // Next song
        document.getElementById('next-song-btn').addEventListener('click', () => this.nextSong());
        
        // Hide suggestions when clicking elsewhere
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#guess-input') && !e.target.closest('#suggestions')) {
                this.hideSuggestions();
            }
        });
    }

    async loadPackages() {
        try {
            const response = await fetch('/api/packages');
            const data = await response.json();
            
            if (data.success) {
                this.renderPackages(data.packages);
            } else {
                this.showError('Failed to load packages: ' + data.error);
            }
        } catch (error) {
            this.showError('Failed to load packages: ' + error.message);
        }
    }

    renderPackages(packages) {
        const packageList = document.getElementById('package-list');
        const loading = document.getElementById('package-loading');
        
        loading.style.display = 'none';
        packageList.innerHTML = '';
        
        packages.forEach(pkg => {
            const col = document.createElement('div');
            col.className = 'col-md-6 col-lg-4 package-checkbox';
            
            col.innerHTML = `
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" value="${pkg}" id="pkg-${pkg}">
                    <label class="form-check-label w-100" for="pkg-${pkg}">
                        <i class="fas fa-folder-music me-2"></i>${pkg}
                    </label>
                </div>
            `;
            
            packageList.appendChild(col);
        });
        
        // Enable start button when packages are selected
        packageList.addEventListener('change', () => {
            const checked = packageList.querySelectorAll('input[type="checkbox"]:checked');
            document.getElementById('start-game-btn').disabled = checked.length === 0;
        });
    }

    showPackageModal() {
        const modal = new bootstrap.Modal(document.getElementById('packageModal'));
        modal.show();
    }

    async startGame() {
        const selectedPackages = Array.from(
            document.querySelectorAll('#package-list input[type="checkbox"]:checked')
        ).map(cb => cb.value);

        if (selectedPackages.length === 0) {
            this.showError('Please select at least one package');
            return;
        }

        // Hide modal and show loading
        bootstrap.Modal.getInstance(document.getElementById('packageModal')).hide();
        document.getElementById('loading-game').style.display = 'block';

        try {
            const response = await fetch('/api/start-game', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    packages: selectedPackages,
                    session_id: this.sessionId
                })
            });

            const data = await response.json();
            
            if (data.success) {
                document.getElementById('loading-game').style.display = 'none';
                this.showGameInterface();
                await this.loadCurrentSong();
            } else {
                this.showError('Failed to start game: ' + data.error);
            }
        } catch (error) {
            this.showError('Failed to start game: ' + error.message);
        }
    }

    showGameInterface() {
        document.getElementById('game-controls').style.display = 'block';
        document.getElementById('guess-section').style.display = 'block';
        document.getElementById('stage-bars').style.display = 'block';
    }

    async loadCurrentSong() {
        try {
            const response = await fetch(`/api/current-song/${this.sessionId}`);
            const data = await response.json();
            
            if (data.success) {
                this.currentSong = data;
                this.currentStage = data.current_stage;
                this.audioManager.currentStage = this.currentStage;
                this.createProgressBars(data.total_stages);
                await this.audioManager.loadStems(data.stems);
                this.updateUI();
            } else {
                this.showError('Failed to load song: ' + data.error);
            }
        } catch (error) {
            this.showError('Failed to load song: ' + error.message);
        }
    }

    createProgressBars(totalStages) {
        const container = document.getElementById('progress-bars');
        container.innerHTML = '';
        
        for (let i = 0; i < totalStages; i++) {
            const barContainer = document.createElement('div');
            barContainer.className = 'progress-bar-container';
            
            barContainer.innerHTML = `
                <div class="progress-bar-label">
                    <span>Stage ${i + 1}</span>
                    <span id="stage-${i}-time">0:00 / 0:30</span>
                </div>
                <div class="progress" data-stage="${i}">
                    <div class="progress-bar" id="progress-${i}" 
                         role="progressbar" style="width: 0%" 
                         aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
                    </div>
                </div>
            `;
            
            container.appendChild(barContainer);
            
            // Add click to seek functionality
            const progressBar = barContainer.querySelector('.progress');
            progressBar.addEventListener('click', (e) => this.seekTo(e, i));
        }
    }

    updateUI() {
        // Update song counter
        const counter = document.getElementById('song-counter');
        counter.textContent = `Stage ${this.currentStage + 1} of ${this.currentSong.total_stages}`;
        
        // Highlight current stage
        document.querySelectorAll('.progress-bar-container').forEach((container, index) => {
            if (index === this.currentStage) {
                container.classList.add('current-stage');
                container.querySelector('.progress-bar').classList.add('active');
            } else {
                container.classList.remove('current-stage');
                container.querySelector('.progress-bar').classList.remove('active');
            }
        });
        
        // Update play/pause button
        const playBtn = document.getElementById('play-pause-btn');
        if (this.isPlaying) {
            playBtn.innerHTML = '<i class="fas fa-pause"></i> Pause';
            playBtn.className = 'btn btn-warning';
        } else {
            playBtn.innerHTML = '<i class="fas fa-play"></i> Play';
            playBtn.className = 'btn btn-success';
        }
    }

async togglePlayPause() {
    if (!this.currentSong) return;

    if (this.isPlaying) {
        if (this.audioManager.isPaused) {
            await this.audioManager.unpause();
            this.audioManager.isPaused = False;
        } else {
            this.audioManager.pause();
            this.audioManager.isPaused = True;
            if (this.progressInterval) clearInterval(this.progressInterval);
        }
        this.updateUI();
        return;
    }
    else{
        
    }

    // Start new playback if not playing
    this.isPlaying = true;
    this.currentProgress = 0;

    try {
        await this.audioManager.play(this.currentStage);
    } catch (e) {
        console.error("Playback load error:", e);
        this.isPlaying = false;
        return;
    }

    this.startProgressTracking();
    this.updateUI();
}


startProgressTracking() {
    if (this.progressInterval) clearInterval(this.progressInterval);

    this.progressInterval = setInterval(() => {
        if (!this.isPlaying) {
            console.log('Not playing, skipping progress update');
            return;
        }

        if (!this.audioManager.isPaused()) {
            const currentTime = this.audioManager.getCurrentTime();
            const duration = this.audioManager.getDuration();

            // Debug logs
            console.log('Progress tracking:', { currentTime, duration, isPaused: this.audioManager.isPaused() });

            if (!duration || duration <= 0) {
                console.warn('Invalid duration:', duration);
                return;
            }

            const progress = (currentTime / duration) * 100;

            const progressBar = document.getElementById(`progress-${this.currentStage}`);
            if (progressBar) {
                progressBar.style.width = `${Math.min(progress, 100)}%`;
                progressBar.setAttribute('aria-valuenow', Math.min(progress, 100));
            } else {
                console.warn('Progress bar element not found for currentStage:', this.currentStage);
            }

            const timeDisplay = document.getElementById(`stage-${this.currentStage}-time`);
            if (timeDisplay) {
                const currentMin = Math.floor(currentTime / 60);
                const currentSec = Math.floor(currentTime % 60);
                const totalMin = Math.floor(duration / 60);
                const totalSec = Math.floor(duration % 60);

                timeDisplay.textContent =
                    `${currentMin}:${currentSec.toString().padStart(2, '0')} / ` +
                    `${totalMin}:${totalSec.toString().padStart(2, '0')}`;
            }

            if (currentTime >= duration) {
                console.log('Playback ended, clearing interval');
                this.isPlaying = false;
                clearInterval(this.progressInterval);
                this.updateUI();
            }
        } else {
            console.log('Audio is paused, not updating progress');
        }
    }, 100);
}

    async skipStage() {
        try {
            const response = await fetch('/api/skip-stage', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: this.sessionId })
            });
            
            const data = await response.json();
            
            if (data.success) {
                if (data.final_stage) {
                    this.showAnswer(data.answer);
                } else {
                    this.currentStage = data.new_stage;
                    this.audioManager.currentStage = this.currentStage;
                    this.audioManager.stop();
                    this.isPlaying = false;
                    this.updateUI();
                    this.clearGuessInput();
                }
            } else {
                this.showError('Failed to skip stage: ' + data.error);
            }
        } catch (error) {
            this.showError('Failed to skip stage: ' + error.message);
        }
    }

    rewind() {
        this.audioManager.rewind(5); // Rewind 5 seconds
    }

    seekTo(event, stage) {
        if (stage !== this.currentStage) return;
        
        const progressBar = event.currentTarget;
        const rect = progressBar.getBoundingClientRect();
        const clickX = event.clientX - rect.left;
        const percentage = clickX / rect.width;
        
        this.audioManager.seekTo(percentage);
    }

    async handleSearchInput() {
        const query = document.getElementById('guess-input').value.trim();
        
        if (query.length < 2) {
            this.hideSuggestions();
            return;
        }
        
        try {
            const response = await fetch('/api/search-songs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showSuggestions(data.suggestions);
            }
        } catch (error) {
            console.error('Search error:', error);
        }
    }

    showSuggestions(suggestions) {
        const suggestionsDiv = document.getElementById('suggestions');
        
        if (suggestions.length === 0) {
            this.hideSuggestions();
            return;
        }
        
        suggestionsDiv.innerHTML = '';
        suggestions.forEach(suggestion => {
            const item = document.createElement('button');
            item.className = 'list-group-item list-group-item-action';
            item.textContent = suggestion.display;
            item.addEventListener('click', () => {
                document.getElementById('guess-input').value = suggestion.display;
                this.hideSuggestions();
            });
            suggestionsDiv.appendChild(item);
        });
        
        suggestionsDiv.style.display = 'block';
    }

    hideSuggestions() {
        document.getElementById('suggestions').style.display = 'none';
    }

    async submitGuess() {
        const guess = document.getElementById('guess-input').value.trim();
        
        if (!guess) {
            this.showFeedback('Please enter a guess!', 'danger');
            return;
        }
        
        try {
            const response = await fetch('/api/guess', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    guess: guess
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                if (data.correct) {
                    this.showCorrectGuess(data.answer, data.points, data.total_score);
                } else {
                    this.showFeedback(data.message, 'warning');
                }
            } else {
                this.showError('Failed to check guess: ' + data.error);
            }
        } catch (error) {
            this.showError('Failed to check guess: ' + error.message);
        }
    }

    showCorrectGuess(answer, points, totalScore) {
        this.showFeedback(`Correct! "${answer}" - You earned ${points} points!`, 'success');
        document.getElementById('score-display').textContent = `Score: ${totalScore}`;
        document.getElementById('next-song-btn').style.display = 'inline-block';
        this.audioManager.stop();
        this.isPlaying = false;
        this.updateUI();
    }

    showAnswer(answer) {
        this.showFeedback(`The answer was: "${answer}"`, 'info');
        document.getElementById('next-song-btn').style.display = 'inline-block';
        this.audioManager.stop();
        this.isPlaying = false;
        this.updateUI();
    }

    async nextSong() {
        try {
            const response = await fetch('/api/next-song', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: this.sessionId })
            });
            
            const data = await response.json();
            
            if (data.success) {
                if (data.game_finished) {
                    this.showGameOver(data.final_score, data.songs_guessed, data.total_songs);
                } else {
                    document.getElementById('song-counter').textContent = 
                        `Song ${data.song_number} of ${data.total_songs}`;
                    document.getElementById('next-song-btn').style.display = 'none';
                    this.clearGuessInput();
                    this.hideFeedback();
                    await this.loadCurrentSong();
                }
            } else {
                this.showError('Failed to load next song: ' + data.error);
            }
        } catch (error) {
            this.showError('Failed to load next song: ' + error.message);
        }
    }

    showGameOver(finalScore, songsGuessed, totalSongs) {
        document.getElementById('game-controls').style.display = 'none';
        document.getElementById('guess-section').style.display = 'none';
        document.getElementById('stage-bars').style.display = 'none';
        
        document.getElementById('final-score').textContent = finalScore;
        document.getElementById('songs-guessed').textContent = songsGuessed;
        document.getElementById('total-songs').textContent = totalSongs;
        document.getElementById('game-over').style.display = 'block';
    }

    clearGuessInput() {
        document.getElementById('guess-input').value = '';
        this.hideSuggestions();
    }

    showFeedback(message, type) {
        const feedback = document.getElementById('feedback');
        feedback.className = `alert alert-${type}`;
        feedback.textContent = message;
        feedback.style.display = 'block';
    }

    hideFeedback() {
        document.getElementById('feedback').style.display = 'none';
    }

    showError(message) {
        this.showFeedback(message, 'danger');
        document.getElementById('loading-game').style.display = 'none';
    }
}

// Initialize game when page loads
document.addEventListener('DOMContentLoaded', () => {
    new KneidelGame();
});
