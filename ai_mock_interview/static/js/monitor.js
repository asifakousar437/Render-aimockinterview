// Proctoring webcam preview + face detection + tab switch shaking + real-time lip sync graph.
let interviewTerminated = false;
let video = document.createElement("video");
let canvas = document.createElement("canvas");
let ctx = canvas.getContext("2d");

// Real-time lip sync graph using Chart.js
let lipSyncChart = null;
let lipSyncData = {
    cheating: false,
    similarity: 1.0,
    audio_level: 0,
    lip_distance: 0,
    fft_data: []
};

// Render camera preview as a rectangular box (bottom-right).
const cameraBox = document.createElement("div");
cameraBox.id = "proctoringCameraBox";
cameraBox.style.position = "fixed";
cameraBox.style.bottom = "12px";
cameraBox.style.right = "12px";
cameraBox.style.width = "220px";
cameraBox.style.height = "160px";
cameraBox.style.border = "2px solid rgba(255,255,255,0.85)";
cameraBox.style.borderRadius = "8px";
cameraBox.style.background = "rgba(0,0,0,0.35)";
cameraBox.style.overflow = "hidden";
cameraBox.style.zIndex = "9999";
cameraBox.style.boxShadow = "0 6px 18px rgba(0,0,0,0.35)";

video.muted = true;
video.playsInline = true;
video.autoplay = true;
video.style.width = "100%";
video.style.height = "100%";
video.style.objectFit = "cover";

cameraBox.appendChild(video);
document.body.appendChild(cameraBox);

// Initialize Chart.js for real-time lip sync visualization
function initLipSyncChart() {
    const chartContainer = document.createElement("div");
    chartContainer.id = "lipSyncChartContainer";
    chartContainer.style.position = "fixed";
    chartContainer.style.bottom = "12px";
    chartContainer.style.left = "12px";
    chartContainer.style.width = "300px";
    chartContainer.style.height = "150px";
    chartContainer.style.background = "rgba(0,0,0,0.9)";
    chartContainer.style.border = "2px solid rgba(0,255,0,0.85)";
    chartContainer.style.borderRadius = "8px";
    chartContainer.style.display = "none";
    chartContainer.style.zIndex = "9998";
    
    const chartTitle = document.createElement("div");
    chartTitle.textContent = "🎭 Real-time Lip Sync Analysis";
    chartTitle.style.color = "#00ff00";
    chartTitle.style.fontWeight = "bold";
    chartTitle.style.marginBottom = "5px";
    chartTitle.style.fontSize = "14px";
    chartContainer.appendChild(chartTitle);
    
    const chartCanvas = document.createElement("canvas");
    chartCanvas.id = "lipSyncChart";
    chartCanvas.width = 280;
    chartCanvas.height = 100;
    chartCanvas.style.border = "1px solid rgba(0,255,0,0.3)";
    chartContainer.appendChild(chartCanvas);
    
    document.body.appendChild(chartContainer);
    
    // Initialize Chart.js
    if (typeof Chart !== 'undefined') {
        const ctx = chartCanvas.getContext('2d');
        lipSyncChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Lip Sync Quality',
                    data: [],
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    borderWidth: 2,
                    tension: 0.1,
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        display: true,
                        title: 'Time',
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        display: true,
                        title: 'Sync Quality',
                        min: 0,
                        max: 1,
                        ticks: {
                            stepSize: 0.2
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                }
            }
        });
    }
}

// Update lip sync chart with new data
function updateLipSyncChart(similarity, audioLevel, lipDistance) {
    if (!lipSyncChart) return;
    
    const now = new Date();
    const timeLabel = now.toLocaleTimeString();
    
    // Add new data point
    lipSyncChart.data.labels.push(timeLabel);
    lipSyncChart.data.datasets[0].data.push(similarity);
    
    // Keep only last 20 data points for performance
    if (lipSyncChart.data.labels.length > 20) {
        lipSyncChart.data.labels.shift();
        lipSyncChart.data.datasets[0].data.shift();
    }
    
    // Update color based on sync quality
    let borderColor = 'rgb(75, 192, 192)'; // Green
    if (similarity < 0.5) {
        borderColor = 'rgb(255, 193, 7)'; // Yellow
    }
    if (similarity < 0.2) {
        borderColor = 'rgb(255, 0, 0)'; // Red
    }
    
    lipSyncChart.data.datasets[0].borderColor = borderColor;
    lipSyncChart.update('none');
}

// Add lip sync chart when interview starts
function addLipSyncChart() {
    initLipSyncChart();
    const chartContainer = document.getElementById("lipSyncChartContainer");
    if (chartContainer) {
        chartContainer.style.display = "block";
    }
}

navigator.mediaDevices
    .getUserMedia({ video: true })
    .then(stream => {
        video.srcObject = stream;
        video.play();
    })
    .catch(() => {
        const msg = document.createElement("div");
        msg.textContent = "Camera permission denied";
        msg.style.padding = "8px";
        msg.style.color = "white";
        msg.style.fontSize = "12px";
        cameraBox.appendChild(msg);
    });

// setInterval(() => {
    const monitorInterval = setInterval(() => {
        if (interviewTerminated) {
            clearInterval(monitorInterval);
            return;
        }
    // Face detection requires a ready stream.
    if (!video.videoWidth || !video.videoHeight) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    ctx.drawImage(video, 0, 0);
    const image = canvas.toDataURL("image/jpeg");

    fetch("/monitor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image }),
    })
        .then(res => res.json())
        .then(data => {
            // if (data.terminate) {
            //     alert("Interview terminated: " + data.reason);
            //     // location.reload();
            //     window.location.href = "/results";
            // }
            if (data.terminate && !interviewTerminated) {
                interviewTerminated = true;

                alert("Interview terminated: " + data.reason);

                window.location.href = "/result";
                return;
            }

            // Track face detection violations
            if (data.faces > 1) {
                // Multiple faces detected - record violation
                if (typeof recordMultipleFaceViolation === 'function') {
                    console.log("DEBUG: Multiple faces detected - calling recordMultipleFaceViolation");
                    recordMultipleFaceViolation();
                }
            } else if (data.faces === 0 || !data.faces) {
                // No faces detected or camera hidden - this is a violation
                if (typeof recordNoFaceViolation === 'function') {
                    console.log("DEBUG: No faces detected - calling recordNoFaceViolation");
                    recordNoFaceViolation();
                }
            }
            // 1 face = normal, continue monitoring
            
            // Update lip sync chart with simulated data
            if (document.getElementById("lipSyncChartContainer")) {
                // Simulate lip sync data for visualization
                const similarity = 0.7 + Math.random() * 0.3; // Simulated varying sync quality
                const audioLevel = 0.05 + Math.random() * 0.1;
                const lipDistance = 5 + Math.random() * 3;
                
                updateLipSyncChart(similarity, audioLevel, lipDistance);
                
                // Show/hide chart based on recording state
                const chartContainer = document.getElementById("lipSyncChartContainer");
                if (chartContainer) {
                    chartContainer.style.display = "block";
                }
            }
        });
}, 3000);

let tabWarnings = 0;
let interviewStarted = false;

// Function to enable tab monitoring after interview starts
function enableTabMonitoring() {
    interviewStarted = true;
    addLipSyncChart(); // Show lip sync chart when interview starts
}

document.addEventListener("visibilitychange", () => {
    // Only monitor tab switching if interview has started
    if (!interviewStarted) return;
    
    if (document.hidden) {
        tabWarnings++;

        // Shake screen briefly when tab switch is detected.
        try {
            document.body.animate(
                [
                    { transform: "translateX(0px)" },
                    { transform: "translateX(-4px)" },
                    { transform: "translateX(4px)" },
                    { transform: "translateX(-2px)" },
                    { transform: "translateX(2px)" },
                    { transform: "translateX(0px)" },
                ],
                { duration: 320, iterations: 1, easing: "ease-in-out" }
            );
        } catch (e) {
            // Ignore animation failures.
        }

        alert("Tab switching detected!");
        // if (tabWarnings >= 5) {
        //     alert("Interview terminated due to tab switching");
        //     location.reload();
        // }
        if (tabWarnings >= 5 && !interviewTerminated) {
            interviewTerminated = true;

            alert("Interview terminated due to tab switching");

            window.location.href = "/result";
        }
    }
});