const form = document.querySelector("#search-form");
const message = document.querySelector("#message");
const results = document.querySelector("#results");

form.addEventListener("submit", async function(event) {
    event.preventDefault();

    const subject = document.querySelector("#subject").value;
    const number = document.querySelector("#number").value.trim();

    message.textContent = "Loading...";
    results.replaceChildren();

    try {
        const response = await fetch(
            `/courses/${encodeURIComponent(subject)}/${encodeURIComponent(number)}`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Search failed");
        }

        message.textContent =
            `${data.course} - ${data.section_count} sections`;

        for (const section of data.sections) {
            const row = document.createElement("tr");

            const values = [
                section.section,
                section.instructor_as_reported,
                section.gpa_reported ?? "N/A",
                section.af_total,
                section.quality_status
            ];

            for (const value of values) {
                const cell = document.createElement("td");
                cell.textContent = String(value);
                row.appendChild(cell);
            }

            results.appendChild(row);
        }

    } catch (error) {
        message.textContent = error.message;
    }
});
