document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".alert").forEach((el) => {
    setTimeout(() => {
      if (el.classList.contains("show")) bootstrap.Alert.getOrCreateInstance(el).close();
    }, 7000);
  });
});
