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

async function typeMessage(role, text) {
    const message = document.createElement("div");
    message.className = `message ${role === "user" ? "user-message" : "ai-message"}`;

    const label = document.createElement("span");
    label.textContent = role === "user" ? "You" : "ChatAI";

    const body = document.createElement("p");

    message.append(label, body);
    chatStream.appendChild(message);

    let current = "";

    // Type raw text
    for (let i = 0; i < text.length; i++) {
        current += text[i];
        body.textContent = current;

        chatStream.scrollTop = chatStream.scrollHeight;

        await new Promise(resolve => setTimeout(resolve, 10));
    }

    // Convert formatting after typing finishes
    body.innerHTML = formatMessage(text);
}
function formatMessage(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.*?)\*/g, "<em>$1</em>")
        .replace(/^### (.*)$/gm, "<h3>$1</h3>")
        .replace(/^## (.*)$/gm, "<h2>$1</h2>")
        .replace(/^# (.*)$/gm, "<h1>$1</h1>")
        .replace(/\n/g, "<br>");
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
    textarea.value = "";
    textarea.focus();

    submitButton.disabled = true;

    try {
        const response = await fetch(form.dataset.chatApi, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ message: text }),
        });

        const data = await response.json();
        await typeMessage(
    "ai",
    response.ok ? data.reply : data.error || "Something went wrong."
);
    } catch (error) {
        await typeMessage("ai", "Unable to reach ChatAI right now.");
    } finally {
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
