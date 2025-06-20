// Audio Manager for Web Audio API
class AudioManager {
    constructor() {
        this.audioContext = null;
        this.stems = [];
        this.loadedBuffers = {};
        this.sources = [];
        this.gainNodes = [];
        this.masterGain = null;
        this.isPlaying = false;
        this.isPaused = false;
        this.startTime = 0;
        this.pauseTime = 0;
        this.duration = 30; // Max 30 seconds per stage
        
        this.initAudioContext();
    }

    async initAudioContext() {
        try {
            // Create audio context
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            // Create master gain node for volume control
            this.masterGain = this.audioContext.createGain();
            this.masterGain.connect(this.audioContext.destination);
            
            // Resume context if suspended (required by some browsers)
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }
        } catch (error) {
            console.error('Failed to initialize audio context:', error);
            throw error;
        }
    }

    async loadStems(stemData) {
        this.stems = stemData;
        this.loadedBuffers = {};
        
        // Load first stem immediately, others can be loaded progressively
        if (stemData.length > 0) {
            await this.loadStem(stemData[0]);
        }
        
        // Load remaining stems in background
        for (let i = 1; i < stemData.length; i++) {
            this.loadStem(stemData[i]).catch(console.error);
        }
    }

    async loadStem(stem) {
        if (this.loadedBuffers[stem.name]) {
            return this.loadedBuffers[stem.name];
        }

        try {
            // Fetch the audio file
            const response = await fetch(stem.url);
            const arrayBuffer = await response.arrayBuffer();
            
            // Decode audio data
            const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
            
            // Store the buffer
            this.loadedBuffers[stem.name] = audioBuffer;
            
            console.log(`Loaded stem: ${stem.name}`);
            return audioBuffer;
            
        } catch (error) {
            console.error(`Failed to load stem ${stem.name}:`, error);
            
            // Create a silent buffer as fallback
            const fallbackBuffer = this.audioContext.createBuffer(2, this.audioContext.sampleRate * this.duration, this.audioContext.sampleRate);
            this.loadedBuffers[stem.name] = fallbackBuffer;
            return fallbackBuffer;
        }
    }

    async play(currentStage) {
        try {
            // Ensure audio context is resumed
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }

            // Stop any current playback
            this.stop();

            // Load required stems for current stage
            const stemsToPlay = this.stems.slice(0, currentStage + 1);
            
            // Ensure all required stems are loaded
            for (const stem of stemsToPlay) {
                if (!this.loadedBuffers[stem.name]) {
                    await this.loadStem(stem);
                }
            }

            // Create source nodes and gain nodes for mixing
            this.sources = [];
            this.gainNodes = [];

            for (const stem of stemsToPlay) {
                const buffer = this.loadedBuffers[stem.name];
                if (!buffer) continue;

                // Create source node
                const source = this.audioContext.createBufferSource();
                source.buffer = buffer;

                // Create gain node for individual stem volume
                const gainNode = this.audioContext.createGain();
                gainNode.gain.setValueAtTime(0.7, this.audioContext.currentTime); // Slightly reduce volume to prevent clipping

                // Connect: source -> gain -> master gain -> destination
                source.connect(gainNode);
                gainNode.connect(this.masterGain);

                this.sources.push(source);
                this.gainNodes.push(gainNode);
            }

            // Start playback
            const startTime = this.isPaused ? this.pauseTime : 0;
            const when = this.audioContext.currentTime;
            
            this.sources.forEach(source => {
                source.start(when, startTime, this.duration - startTime);
            });

            this.startTime = this.audioContext.currentTime - startTime;
            this.isPlaying = true;
            this.isPaused = false;

            // Auto-stop after duration
            setTimeout(() => {
                if (this.isPlaying && !this.isPaused) {
                    this.stop();
                }
            }, (this.duration - startTime) * 1000);

        } catch (error) {
            console.error('Playback error:', error);
            throw error;
        }
    }

    pause() {
        if (!this.isPlaying || this.isPaused) return;

        this.sources.forEach(source => {
            try {
                source.stop();
            } catch (e) {
                // Source might already be stopped
            }
        });

        this.pauseTime = this.getCurrentTime();
        this.isPaused = true;
        this.isPlaying = false;
    }

    stop() {
        this.sources.forEach(source => {
            try {
                source.stop();
            } catch (e) {
                // Source might already be stopped
            }
        });

        this.sources = [];
        this.gainNodes = [];
        this.isPlaying = false;
        this.isPaused = false;
        this.startTime = 0;
        this.pauseTime = 0;
    }

    rewind(seconds) {
        if (!this.isPlaying && !this.isPaused) return;

        const currentTime = this.getCurrentTime();
        const newTime = Math.max(0, currentTime - seconds);
        
        this.pauseTime = newTime;
        
        if (this.isPlaying) {
            // Restart playback from new position
            this.pause();
            this.play(this.getCurrentStage()).catch(console.error);
        }
    }

    seekTo(percentage) {
        if (!this.isPlaying && !this.isPaused) return;

        const newTime = percentage * this.duration;
        this.pauseTime = Math.max(0, Math.min(newTime, this.duration));
        
        if (this.isPlaying) {
            // Restart playback from new position
            this.pause();
            this.play(this.getCurrentStage()).catch(console.error);
        }
    }

    getCurrentTime() {
        if (this.isPaused) {
            return this.pauseTime;
        } else if (this.isPlaying) {
            return Math.min(this.audioContext.currentTime - this.startTime, this.duration);
        }
        return 0;
    }

    getDuration() {
        return this.duration;
    }

    getCurrentStage() {
        // This should be set by the game logic
        return this.currentStage || 0;
    }

    setMasterVolume(volume) {
        if (this.masterGain) {
            this.masterGain.gain.setValueAtTime(volume, this.audioContext.currentTime);
        }
    }

    // Utility method to check if Web Audio API is supported
    static isSupported() {
        return !!(window.AudioContext || window.webkitAudioContext);
    }
}

// Initialize audio on first user interaction (required by browsers)
document.addEventListener('click', function initAudio() {
    if (window.audioManager && window.audioManager.audioContext) {
        window.audioManager.audioContext.resume();
    }
    document.removeEventListener('click', initAudio);
}, { once: true });
