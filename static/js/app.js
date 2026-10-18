document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.getAttribute("data-confirm"))) event.preventDefault();
    });
  });
  document.querySelectorAll('input[type="number"]').forEach((input) => {
    input.addEventListener("input", () => {
      const value = Number(input.value);
      input.setCustomValidity(input.value !== "" && (value < 0 || value > 100)
        ? "Enter a value between 0 and 100." : "");
    });
  });
});
