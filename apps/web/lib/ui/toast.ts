const TOAST_ID = "c2pro-global-toast";

export const showToast = (message: string) => {
  if (typeof window === "undefined") {
    return;
  }

  const existingToast = document.getElementById(TOAST_ID);
  if (existingToast) {
    existingToast.textContent = message;
    return;
  }

  const toast = document.createElement("div");
  toast.id = TOAST_ID;
  toast.textContent = message;
  toast.style.position = "fixed";
  toast.style.right = "24px";
  toast.style.bottom = "24px";
  toast.style.zIndex = "9999";
  toast.style.background = "rgba(17, 24, 39, 0.95)";
  toast.style.color = "#fff";
  toast.style.padding = "12px 16px";
  toast.style.borderRadius = "12px";
  toast.style.fontSize = "14px";
  toast.style.boxShadow = "0 10px 20px rgba(0, 0, 0, 0.25)";
  toast.style.transition = "opacity 200ms ease";
  toast.style.opacity = "0";

  document.body.appendChild(toast);

  requestAnimationFrame(() => {
    toast.style.opacity = "1";
  });

  window.setTimeout(() => {
    toast.style.opacity = "0";
    window.setTimeout(() => {
      toast.remove();
    }, 200);
  }, 2400);
};
