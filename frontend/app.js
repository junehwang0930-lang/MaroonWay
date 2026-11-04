
const form = document.querySelector("#search-form");
const message = document.querySelector("#message");
const results = document.querySelector("#results");

const dialog = document.querySelector("#section-dialog");
const closeButton = document.querySelector("#close-dialog");

// Close the popup when X is clicked
closeButton.addEventListener("click", function() {
    dialog.close();
});

// Create a grade distribution bar
function createGradeBar(section) {
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

    for (const [grade, count] of grades) {
        const percentage = section.af_total > 0
            ? (count / section.af_total) * 100
            : 0;

        descriptions.push(
            `${grade}: ${count} students (${percentage.toFixed(1)}%)`
        );

        if (count === 0) {
            continue;
        }

        const segment = document.createElement("div");

        segment.className =
            `grade-segment grade-${grade.toLowerCase()}`;

        segment.style.width = `${percentage}%`;

        segment.title =
            `${grade}: ${count} students (${percentage.toFixed(1)}%)`;

        gradeBar.appendChild(segment);
    }

    gradeBar.setAttribute("role", "img");
    gradeBar.setAttribute(
        "aria-label",
        descriptions.join(", ")
    );

    return gradeBar;
}

// Open the selected section's detail popup
function showSectionDetails(course, section) {
    document.querySelector("#detail-title").textContent =
        `${course} - Section ${section.section}`;

    document.querySelector("#detail-instructor").textContent =
        `Instructor: ${section.instructor_as_reported}`;

    document.querySelector("#detail-gpa").textContent =
        section.gpa_reported ?? "N/A";

    document.querySelector("#detail-students").textContent =
        section.af_total;

    // Display a larger grade bar
    const gradeBar = createGradeBar(section);
    gradeBar.classList.add("detail-grade-bar");

    document.querySelector("#detail-bar-container")
        .replaceChildren(gradeBar);

    // Display grade counts and percentages
    const gradeList = document.querySelector("#detail-grades");
    gradeList.replaceChildren();

    const grades = [
        ["A", section.a],
        ["B", section.b],
        ["C", section.c],
        ["D", section.d],
        ["F", section.f]
    ];

    for (const [grade, count] of grades) {
        const percentage = section.af_total > 0
            ? (count / section.af_total) * 100
            : 0;

        const item = document.createElement("div");
        item.className = "grade-detail-item";

        const dot = document.createElement("span");
        dot.className =
            `grade-dot grade-${grade.toLowerCase()}`;

        const label = document.createElement("span");
        label.textContent =
            `${grade}: ${count} (${percentage.toFixed(1)}%)`;

        item.appendChild(dot);
        item.appendChild(label);
        gradeList.appendChild(item);
    }

    // Explain the data quality status
    const status = document.querySelector("#detail-status");

    if (section.quality_status === "needs_review") {
        status.textContent =
            "Needs Review: An automatic check flagged this record.";
    } else {
        status.textContent =
            "Checks Passed: No automatic validation issue was flagged.";
    }

    // Show the popup
    dialog.showModal();
}

// Search for courses
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

            // Create a clickable Section number
            const sectionCell = document.createElement("td");
            const sectionButton = document.createElement("button");

            sectionButton.type = "button";
            sectionButton.className = "section-link";
            sectionButton.textContent = section.section;

            sectionButton.addEventListener("click", function() {
                showSectionDetails(data.course, section);
            });

            sectionCell.appendChild(sectionButton);
            row.appendChild(sectionCell);

            // Add the other table columns
            const values = [
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

            // Add the grade distribution bar
            const gradeCell = document.createElement("td");
            gradeCell.appendChild(createGradeBar(section));
            row.appendChild(gradeCell);

            // Add the completed row to the table
            results.appendChild(row);
        }

    } catch (error) {
        message.textContent = error.message;
    }
});
