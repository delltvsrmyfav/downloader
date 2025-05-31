// Main JavaScript file for YouTube to Drive app

// Theme management
const themeToggle = document.getElementById('themeToggle');
const html = document.documentElement;

// Use a simple variable instead of localStorage for Flask environment
// let currentTheme = 'dark'; // Default theme - Your HTML sets data-theme="dark" initially, so we'll rely on that.

// Get initial theme from HTML data-attribute
let currentTheme = html.getAttribute('data-theme') || 'dark';


// Set initial theme based on the variable
html.setAttribute('data-theme', currentTheme);

if (themeToggle) {
    // Set initial icon based on initial theme
    const initialIcon = themeToggle.querySelector('i');
    if (initialIcon) {
        initialIcon.className = currentTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    }

    themeToggle.addEventListener('click', () => {
        currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-theme', currentTheme);

        // Update button icon
        const icon = themeToggle.querySelector('i');
        if (icon) {
            icon.className = currentTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    });
}

// Global variables
let currentVideoData = null;
let isDownloading = false;
let currentDownloadedVideos = []; // To store fetched downloaded videos
let socket; // Declare socket globally for real-time updates

// Get DOM elements for video info and download
const urlInput = document.getElementById('urlInput');
const getInfoBtn = document.getElementById('getInfoBtn');
const loadingSpinner = document.getElementById('loadingSpinner');
const errorContainer = document.getElementById('errorContainer');
const errorMessage = document.getElementById('errorMessage');
const successContainer = document.getElementById('successContainer');
const successMessage = document.getElementById('successMessage');
const videoInfoContainer = document.getElementById('videoInfo'); // Original ID
const videoThumbnail = document.getElementById('videoThumbnail');
const videoTitle = document.getElementById('videoTitle');
const videoChannel = document.getElementById('videoChannel');
const videoDuration = document.getElementById('videoDuration');
const videoViews = document.getElementById('videoViews');
const videoUploadDate = document.getElementById('videoUploadDate'); // New
const videoDescription = document.getElementById('videoDescription');
const summarizeBtn = document.getElementById('summarizeBtn'); // New
const summaryContainer = document.getElementById('summaryContainer'); // New
const videoSummary = document.getElementById('videoSummary'); // New
const qualitySelect = document.getElementById('qualitySelect');
const downloadBtn = document.getElementById('downloadBtn');
const externalLink = document.getElementById('externalLink'); // New

// Get DOM elements for progress bar
const progressBarContainer = document.getElementById('progressBarContainer');
const progressBar = document.getElementById('progressBar');
const progressText = document.getElementById('progressText');
const progressMessage = document.getElementById('progressMessage');
const downloadLinkContainer = document.getElementById('downloadLinkContainer');
const downloadLink = document.getElementById('downloadLink');


// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    setupEventListeners();
    // Removed checkAuthStatus(); // No longer needed
    addLoadingAnimations();
    // Establish Socket.IO connection
    socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);
    socket.on('progress_update', handleProgressUpdate); // Listen to 'progress_update' as per app.py now
    socket.on('download_complete', handleDownloadComplete); // Listen for download completion
    socket.on('download_error', handleDownloadError); // Listen for download errors
    socket.on('connect', () => {
        console.log('Socket.IO Connected!');
        // No specific UI update for connect, handled by Flask's initial 'status_update'
    });
    socket.on('status_update', (data) => { // This is for initial server status messages
        console.log('Server Status:', data.message);
        // You might want a general status area in your UI for this
        // For now, it just logs
    });
}

function setupEventListeners() {
    getInfoBtn.addEventListener('click', getInfo);
    urlInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            getInfo();
        }
    });
    downloadBtn.addEventListener('click', startDownload);
    summarizeBtn.addEventListener('click', summarizeDescription); // New event listener for summarize button
}

// --- Helper Functions ---
function showLoading() {
    loadingSpinner.style.display = 'block';
    hideVideoInfo();
    hideError();
    hideSuccess();
    progressBarContainer.style.display = 'none'; // Hide progress bar
    downloadLinkContainer.style.display = 'none'; // Hide download link
}

function hideLoading() {
    loadingSpinner.style.display = 'none';
}

function showError(message) {
    errorContainer.style.display = 'block';
    errorMessage.textContent = message;
    errorContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function hideError() {
    errorContainer.style.display = 'none';
    errorMessage.textContent = '';
}

function showSuccess(message) {
    successContainer.style.display = 'block';
    successMessage.textContent = message;
    successContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(() => {
        successContainer.style.display = 'none';
    }, 5000);
}

function hideSuccess() {
    successContainer.style.display = 'none';
}

function hideVideoInfo() {
    videoInfoContainer.style.display = 'flex'; // Ensure it's flex when visible, display none when hidden
    summaryContainer.style.display = 'none'; // Hide summary when hiding video info
    videoInfoContainer.style.display = 'none'; // Re-hide the main video info container
}

function resetForm() {
    urlInput.value = '';
    hideVideoInfo();
    // resetDownloadButton(); // Not explicitly needed, as downloadBtn state changes
    currentVideoData = null;
    hideSuccess();
    hideError();
    progressBarContainer.style.display = 'none'; // Reset progress bar visibility
    downloadLinkContainer.style.display = 'none'; // Reset download link visibility
    progressBar.style.width = '0%';
    progressText.textContent = '0%';
    progressMessage.textContent = 'Starting...';
}

// Format duration from seconds to HH:MM:SS
function formatDuration(seconds) {
    if (isNaN(seconds) || seconds < 0) return 'N/A';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    
    let parts = [];
    if (hours > 0) parts.push(hours + 'h');
    if (minutes > 0 || hours > 0) parts.push(minutes + 'm'); // show minutes if hours exist or if minutes are present
    parts.push(remainingSeconds + 's');
    
    return parts.join(' ');
}

// Format filesize from bytes to human-readable string
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    if (bytes === null || bytes === undefined) return 'N/A';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// --- Main Functions ---

async function getInfo() {
    const url = urlInput.value.trim();
    if (!url) {
        showError('Please enter a YouTube video URL.');
        return;
    }

    showLoading();
    hideError();
    hideSuccess();
    downloadBtn.disabled = true; // Disable download button during info fetching

    try {
        const response = await fetch('/get_video_info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        });
        const data = await response.json();

        if (response.ok) {
            currentVideoData = data;
            displayVideoInfo(data);
            showSuccess('Video information loaded!');
        } else {
            showError(data.error || 'Failed to get video info.');
            currentVideoData = null;
        }
    } catch (error) {
        console.error('Error fetching video info:', error);
        showError('An unexpected error occurred while fetching video information. Please try again.');
        currentVideoData = null;
    } finally {
        hideLoading();
        downloadBtn.disabled = false; // Re-enable download button
    }
}

function displayVideoInfo(data) {
    videoInfoContainer.style.display = 'flex'; // Use flex based on your CSS
    videoThumbnail.src = data.thumbnail;
    videoTitle.textContent = data.title;
    videoChannel.innerHTML = `<i class="fas fa-user"></i> ${data.channel}`;
    videoDuration.innerHTML = `<i class="fas fa-clock"></i> ${formatDuration(data.duration)}`;
    videoViews.innerHTML = `<i class="fas fa-eye"></i> ${data.view_count.toLocaleString()}`;
    
    // Format upload date if available (YYYYMMDD to YYYY-MM-DD)
    if (data.upload_date && data.upload_date.length === 8) {
        const year = data.upload_date.substring(0, 4);
        const month = data.upload_date.substring(4, 6);
        const day = data.upload_date.substring(6, 8);
        videoUploadDate.innerHTML = `<i class="fas fa-calendar-alt"></i> ${year}-${month}-${day}`;
        videoUploadDate.style.display = 'inline-block'; // Ensure it's visible
    } else {
        videoUploadDate.style.display = 'none'; // Hide if no date
    }

    videoDescription.textContent = data.description; // Display full description

    // Set original video link
    if (data.webpage_url) {
        externalLink.href = data.webpage_url;
        externalLink.style.display = 'inline-flex'; // Use inline-flex for button
    } else {
        externalLink.style.display = 'none';
    }


    // Populate quality selection dropdown
    qualitySelect.innerHTML = '<option value="">Select Quality</option>'; // Clear previous options
    
    // Filter and sort formats for display
    // Keep only video streams with height or audio streams (if no video stream combined)
    const relevantFormats = data.formats.filter(f => f.height || f.resolution === "Audio");

    relevantFormats.forEach(format => {
        const option = document.createElement('option');
        option.value = format.format_id;
        
        let qualityText = "";
        if (format.height) {
            qualityText = `${format.height}p`; // e.g., "720p", "1080p"
        } else if (format.resolution === "Audio") {
            qualityText = `Audio`;
            if (format.acodec) qualityText += ` (${format.acodec})`;
        } else {
            qualityText = format.quality; // Fallback to generic quality string
        }

        if (format.vcodec && format.vcodec !== 'none' && format.ext) { // Add video codec and ext for video streams
            qualityText += ` (.${format.ext})`;
        } else if (format.acodec && format.acodec !== 'none' && format.ext && format.resolution !== "Audio") { // Add audio ext if it's a combined stream
             qualityText += ` (.${format.ext})`;
        } else if (format.ext && format.resolution === "Audio") { // Add audio ext for audio-only streams
            qualityText += ` (.${format.ext})`;
        }


        if (format.filesize) {
            qualityText += ` - ${formatFileSize(format.filesize)}`;
        }
        option.textContent = qualityText;
        qualitySelect.appendChild(option);
    });

    // Attempt to pre-select 720p, otherwise select the first available (highest quality from sorted list)
    const seventyTwoOp = relevantFormats.find(f => f.height === 720);
    if (seventyTwoOp) {
        qualitySelect.value = seventyTwoOp.format_id;
    } else if (relevantFormats.length > 0) {
        qualitySelect.value = relevantFormats[0].format_id;
    }
}

async function summarizeDescription() {
    if (!currentVideoData) {
        showError('No video information available to summarize.');
        return;
    }

    summaryContainer.style.display = 'block';
    videoSummary.textContent = 'Generating summary...';
    summaryContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    try {
        const response = await fetch('/summarize_video', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                title: currentVideoData.title,
                description: currentVideoData.description 
            })
        });
        const data = await response.json();

        if (response.ok) {
            // Use marked.js if you want Markdown rendering, otherwise just textContent
            videoSummary.innerHTML = marked.parse(data.summary);
            // videoSummary.textContent = data.summary;
        } else {
            videoSummary.textContent = `Error summarizing: ${data.error}`;
        }
    } catch (error) {
        console.error('Error summarizing video:', error);
        videoSummary.textContent = 'An error occurred while generating the summary.';
    }
}

function startDownload() {
    if (!currentVideoData) {
        showError('Please get video information first.');
        return;
    }

    const selectedFormatId = qualitySelect.value;
    if (!selectedFormatId) {
        showError('Please select a quality for download.');
        return;
    }

    if (isDownloading) {
        showError('A download is already in progress. Please wait.');
        return;
    }

    isDownloading = true;
    downloadBtn.disabled = true;
    getInfoBtn.disabled = true;
    urlInput.disabled = true;
    qualitySelect.disabled = true;
    summarizeBtn.disabled = true;

    hideVideoInfo(); // Hide video info when download starts
    hideError();
    hideSuccess();
    progressBarContainer.style.display = 'block'; // Show progress bar
    downloadLinkContainer.style.display = 'none'; // Hide download link until complete
    downloadLink.href = '#'; // Clear previous link
    downloadLink.textContent = ''; // Clear previous link text
    progressBar.style.width = '0%';
    progressText.textContent = '0%';
    progressMessage.textContent = 'Starting download...';
    progressBarContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });


    console.log('Emitting start_download event...');
    socket.emit('start_download', {
        video_url: currentVideoData.original_url,
        format_id: selectedFormatId,
        video_title: currentVideoData.title
    });
}

// --- Socket.IO Handlers ---
function handleProgressUpdate(data) {
    console.log('Progress Update:', data);
    const progress = Math.round(data.progress);
    const message = data.message;

    progressBar.style.width = progress + '%';
    progressText.textContent = `${progress}%`;
    progressMessage.textContent = message;

    // Optional: Hide/show based on status
    if (data.status === 'downloading') {
        progressBarContainer.style.display = 'block';
        downloadLinkContainer.style.display = 'none';
    } else if (data.status === 'finished') {
        progressMessage.textContent = 'Download completed successfully. Preparing link...';
    }
}

function handleDownloadComplete(data) {
    console.log('Download Complete:', data);
    isDownloading = false;
    downloadBtn.disabled = false;
    getInfoBtn.disabled = false;
    urlInput.disabled = false;
    qualitySelect.disabled = false;
    summarizeBtn.disabled = false;


    showSuccess('Download completed successfully!');
    progressMessage.textContent = data.message; // "Download completed successfully!" from app.py

    // Display the downloadable link
    downloadLink.href = data.file_url;
    downloadLink.textContent = `Download "${data.filename}"`; // Set more descriptive text
    downloadLinkContainer.style.display = 'block';
    
    // Scroll to the download link
    downloadLinkContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Optionally: reset form after a short delay or prompt user
    // setTimeout(resetForm, 5000);
}

function handleDownloadError(data) {
    console.error('Download Error:', data);
    isDownloading = false;
    downloadBtn.disabled = false;
    getInfoBtn.disabled = false;
    urlInput.disabled = false;
    qualitySelect.disabled = false;
    summarizeBtn.disabled = false;

    showError(`Download failed: ${data.message}`);
    progressBarContainer.style.display = 'none'; // Hide progress bar on error
    downloadLinkContainer.style.display = 'none'; // Hide download link on error
    progressMessage.textContent = `Error: ${data.message}`; // Update message for persistent display
}


// --- Remaining Original Functions (Keep these as they are from your original main.js) ---
// (No changes needed for these, they handle UI and auth not directly related to download process)

// Removed checkAuthStatus function entirely.

function addLoadingAnimations() {
    const inputs = document.querySelectorAll('input');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
        });

        input.addEventListener('blur', function() {
            this.parentElement.classList.remove('focused');
        });
    });
}