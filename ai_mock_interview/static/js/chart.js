// Get scores from localStorage (fallback) or use empty array
const scores = JSON.parse(localStorage.getItem("scores")) || [];

document.addEventListener('DOMContentLoaded', function() {
    const ctx = document.getElementById("chart");
    
    if (ctx && scores.length > 0) {
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: scores.map((_, i) => "Q" + (i + 1)),
                datasets: [{
                    label: 'Score',
                    data: scores,
                    backgroundColor: scores.map(score => 
                        score >= 4 ? 'rgba(40, 167, 69, 0.8)' : 
                        score >= 3 ? 'rgba(255, 193, 7, 0.8)' : 
                        'rgba(220, 53, 69, 0.8)'
                    ),
                    borderColor: scores.map(score => 
                        score >= 4 ? 'rgba(40, 167, 69, 1)' : 
                        score >= 3 ? 'rgba(255, 193, 7, 1)' : 
                        'rgba(220, 53, 69, 1)'
                    ),
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Score: ${context.parsed.y}/5`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 5,
                        ticks: {
                            stepSize: 1
                        },
                        title: {
                            display: true,
                            text: 'Score (out of 5)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Question Number'
                        }
                    }
                }
            }
        });
    } else if (ctx) {
        // Show message if no scores available
        ctx.parentElement.innerHTML += '<p style="text-align: center; color: #666;">No score data available</p>';
    }
});