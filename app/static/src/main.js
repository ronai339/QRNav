document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("darkToggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      document.documentElement.classList.toggle("dark");
      console.log("Dark mode toggled")
    })
  }
  else {
      console.warn("Dark toggle button not found.");
  }
});