const btn = document.getElementById("verify-btn");
const result = document.getElementById("result");
const actionLog = document.getElementById("action-log");
const input = document.getElementById("code-input");

function runSpecificActionScript(code) {
  document.body.style.background = "#eef5ff";
  actionLog.textContent =
    `Specific script executed for ${code}:\n` +
    "- Session action token prepared\n" +
    "- Follow-up automation step triggered\n" +
    "- Audit log marker recorded";
}

btn.addEventListener("click", async () => {
  const code = (input.value || "").trim().toUpperCase();
  if (!code) {
    result.textContent = "Enter a code first.";
    return;
  }

  const res = await fetch(`/codes/verify/${encodeURIComponent(code)}`);
  const payload = await res.json();
  result.textContent = payload.message;

  if (payload.exists) {
    runSpecificActionScript(payload.code);
  } else {
    actionLog.textContent = "No action script executed because code does not exist.";
  }
});
