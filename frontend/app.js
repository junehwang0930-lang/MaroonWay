
const form = document.querySelector("#search-form");
const message = document.querySelector("#message");
const results = document.querySelector("#results");

form.addEventListener("submit", async function(event) {
    event.preventDefault();

    // 1. Get course information from user inputs
    const subject = document.querySelector("#subject").value;
    const number = document.querySelector("#number").value.trim();

    message.textContent = "Loading...";
    results.replaceChildren();

    try {
        // 2. Request course data from FastAPI
        const response = await fetch(
            `/courses/${encodeURIComponent(subject)}/${encodeURIComponent(number)}`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Search failed");
        }

        // 3. Display search result summary
        message.textContent =
            `${data.course} - ${data.section_count} sections`;

        // 4. Create one table row for each section
        for (const section of data.sections) {
            const row = document.createElement("tr");

            const values = [
                section.section,
                section.instructor_as_reported,
                section.gpa_reported ?? "N/A",
                section.af_total,
                section.quality_status
            ];

            // 5. Add regular table cells
            for (const value of values) {
                const cell = document.createElement("td");
                cell.textContent = String(value);
                row.appendChild(cell);
            }

            // 6. Create a Grade Distribution cell
            const gradeCell = document.createElement("td");
            const gradeBar = document.createElement("div");

            gradeBar.className = "grade-bar";

            const grades = [
                ["A", section.a],
                ["B", section.b],
                ["C", section.c],
                ["D", section.d],
                ["F", section.f]
            ];

            const descriptions = [];

            // 7. Create a colored segment for each grade
            for (const [grade, count] of grades) {
                const percentage = section.af_total > 0
                    ? (count / section.af_total) * 100
                    : 0;

                const segment = document.createElement("div");

                segment.className =
                    `grade-segment grade-${grade.toLowerCase()}`;

                segment.style.width = `${percentage}%`;

                segment.title =
                    `${grade}: ${count} students (${percentage.toFixed(1)}%)`;

                gradeBar.appendChild(segment);
                descriptions.push(segment.title);
            }

            // 8. Add accessibility information
            gradeBar.setAttribute("role", "img");
            gradeBar.setAttribute(
                "aria-label",
                descriptions.join(", ")
            );

            // 9. Add the grade bar to the table row
            gradeCell.appendChild(gradeBar);
            row.appendChild(gradeCell);

            // 10. Display the completed row
            results.appendChild(row);
        }

    } catch (error) {
        message.textContent = error.message;
    }
});
