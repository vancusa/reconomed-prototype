//Shared small helpers
// utils.js
export function formatDate(date = new Date()) {
  return date.toLocaleDateString(undefined, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
}

export function formatDateTime(date = new Date()) {
  return date.toLocaleString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

export function showCurrentDate(elementId = 'current-date') {
  const el = document.getElementById(elementId);
  if (el) {
    el.textContent = formatDate();
  }
}

export function startLiveClock(elementId = 'date-time') {
  const el = document.getElementById(elementId);
  if (!el) return;

  function update() {
    el.textContent = formatDateTime(new Date());
  }
  update();
  setInterval(update, 1000);
}
