const menuButton = document.querySelector(".menu-toggle");
const navLinks = document.querySelector(".nav-links");

if (menuButton && navLinks) {
    menuButton.addEventListener("click", () => {
        const isOpen = navLinks.classList.toggle("open");
        menuButton.setAttribute("aria-expanded", String(isOpen));
    });

    navLinks.addEventListener("click", (event) => {
        if (event.target.tagName === "A") {
            navLinks.classList.remove("open");
            menuButton.setAttribute("aria-expanded", "false");
        }
    });
}

const chatForm = document.querySelector("[data-chat-form]");
const chatStream = document.querySelector("[data-chat-stream]");
const thinkingIndicator = document.querySelector("[data-thinking-indicator]");

function setThinking(isThinking) {
    if (!thinkingIndicator) return;

    if (isThinking) {
        // Keep the status directly below the most recent user message, where the reply will appear.
        chatStream.appendChild(thinkingIndicator);
    }
    thinkingIndicator.hidden = !isThinking;
    chatStream.scrollTop = chatStream.scrollHeight;
}

function appendAiMessage(text) {
    const message = document.createElement("div");
    message.className = "message ai-message";

    const label = document.createElement("span");
    label.textContent = "ChatAI";

    const body = document.createElement("p");
    body.innerHTML = formatMessage(text);

    message.append(label, body);
    chatStream.appendChild(message);
    chatStream.scrollTop = chatStream.scrollHeight;
}
function formatMessage(text) {
    const escaped = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

    return escaped
        // Only ByteSona article anchors are allowed as clickable chat links.
        .replace(/\[([^\]]+)\]\(\/news#article-(\d+)\)/g, '<a href="/news#article-$2">$1</a>')
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>")
        .replace(/^### (.*)$/gm, "<h3>$1</h3>")
        .replace(/^## (.*)$/gm, "<h2>$1</h2>")
        .replace(/^# (.*)$/gm, "<h1>$1</h1>")
        .replace(/\n/g, "<br>");
}

document.querySelectorAll("[data-ai-content]").forEach((message) => {
    message.innerHTML = formatMessage(message.textContent);
});

if (chatStream) {
    chatStream.scrollTop = chatStream.scrollHeight;
}

function appendMessage(role, text) {
    const emptyChat = document.querySelector("[data-empty-chat]");
    if (emptyChat) {
        emptyChat.remove();
    }

    const message = document.createElement("div");
    message.className = `message ${role === "user" ? "user-message" : "ai-message"}`;

    const label = document.createElement("span");
    label.textContent = role === "user" ? "You" : "ChatAI";

    const body = document.createElement("p");
    body.textContent = text;

    message.append(label, body);
    chatStream.appendChild(message);
    chatStream.scrollTop = chatStream.scrollHeight;
}

async function sendChatMessage(form) {
    const textarea = form.querySelector("textarea[name='message']");
    const submitButton = form.querySelector("button[type='submit']");
    const text = textarea.value.trim();

    if (!text) {
        textarea.focus();
        return;
    }

    appendMessage("user", text);
    document.querySelector("[data-quick-questions]")?.remove();
    textarea.value = "";
    textarea.focus();

    submitButton.disabled = true;
    setThinking(true);

    try {
        const response = await fetch(form.dataset.chatApi, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ message: text }),
        });

        const data = await response.json();
        setThinking(false);
        appendAiMessage(response.ok ? data.reply : data.error || "Something went wrong.");
    } catch (error) {
        setThinking(false);
        appendAiMessage("Unable to reach ChatAI right now.");
    } finally {
        setThinking(false);
        submitButton.disabled = false;
    }
}

if (chatForm && chatStream) {
    const textarea = chatForm.querySelector("textarea[name='message']");

    chatForm.addEventListener("submit", (event) => {
        event.preventDefault();
        sendChatMessage(chatForm);
    });

    textarea.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            sendChatMessage(chatForm);
        }
    });
}

document.querySelectorAll("[data-quick-question]").forEach((button) => {
    button.addEventListener("click", () => {
        if (!chatForm) return;
        const textarea = chatForm.querySelector("textarea[name='message']");
        textarea.value = button.dataset.quickQuestion;
        sendChatMessage(chatForm);
    });
});
