
const form = document.querySelector("#search-form");
const message = document.querySelector("#message");
const results = document.querySelector("#results");

const compareButton = document.querySelector("#compare-button");
const selectionCount = document.querySelector("#selection-count");
const compareDialog = document.querySelector("#compare-dialog");

const selected = new Map();
let currentCourse = "";

// Calculate a percentage
function percent(part, total) {
    if (total === 0) return "N/A";
    return `${(part / total * 100).toFixed(1)}%`;
}

// Create a colored grade bar
function createGradeBar(section) {
    const bar = document.createElement("div");
    bar.className = "grade-bar";

    const grades = [
        ["A", section.a],
        ["B", section.b],
        ["C", section.c],
        ["D", section.d],
        ["F", section.f]
    ];

    const descriptions = [];

    for (const [grade, count] of grades) {
        const rate = percent(count, section.af_total);
        descriptions.push(`${grade}: ${count} (${rate})`);

        if (count === 0) continue;

        const segment = document.createElement("div");
        segment.className =
            `grade-segment grade-${grade.toLowerCase()}`;

        segment.style.width =
            `${count / section.af_total * 100}%`;

        segment.title = `${grade}: ${count} (${rate})`;
        bar.appendChild(segment);
    }

    bar.setAttribute("role", "img");
    bar.setAttribute("aria-label", descriptions.join(", "));

    return bar;
}

// Enable Compare only when exactly two sections are selected
function updateSelection() {
    selectionCount.textContent =
        `${selected.size} of 2 sections selected`;

    compareButton.disabled = selected.size !== 2;

    document.querySelectorAll(".compare-checkbox")
        .forEach(function(checkbox) {
            checkbox.disabled =
                selected.size === 2 && !checkbox.checked;
        });
}

// Add one comparison row
function addCompareRow(label, left, right) {
    const row = document.createElement("tr");

    for (const value of [label, left, right]) {
        const cell = document.createElement("td");
        cell.textContent = String(value);
        row.appendChild(cell);
    }

    document.querySelector("#compare-results").appendChild(row);
}

// Open the comparison popup
compareButton.addEventListener("click", function() {
    if (selected.size !== 2) return;

    const [left, right] = [...selected.values()];

    document.querySelector("#compare-course").textContent =
        `${currentCourse} · Spring 2026`;

    document.querySelector("#compare-left-title").textContent =
        `Section ${left.section}`;

    document.querySelector("#compare-right-title").textContent =
        `Section ${right.section}`;

    const body = document.querySelector("#compare-results");
    body.replaceChildren();

    addCompareRow(
        "Instructor",
        left.instructor_as_reported,
        right.instructor_as_reported
    );

    addCompareRow(
        "Reported GPA",
        left.gpa_reported ?? "N/A",
        right.gpa_reported ?? "N/A"
    );

    addCompareRow("A-F Students", left.af_total, right.af_total);

    addCompareRow(
        "A Rate",
        percent(left.a, left.af_total),
        percent(right.a, right.af_total)
    );

    addCompareRow(
        "D + F Rate",
        percent(left.d + left.f, left.af_total),
        percent(right.d + right.f, right.af_total)
    );

    addCompareRow("Q-Drops", left.q_count, right.q_count);

    addCompareRow(
        "Q Share",
        percent(left.q_count, left.enrollment_total),
        percent(right.q_count, right.enrollment_total)
    );

    addCompareRow(
        "Reported Total",
        left.enrollment_total,
        right.enrollment_total
    );

    addCompareRow(
        "Data Status",
        left.quality_status,
        right.quality_status
    );

    // Add grade distribution bars
    const row = document.createElement("tr");
    const label = document.createElement("td");
    label.textContent = "Grade Distribution";
    row.appendChild(label);

    for (const section of [left, right]) {
        const cell = document.createElement("td");
        cell.appendChild(createGradeBar(section));
        row.appendChild(cell);
    }

    body.appendChild(row);
    compareDialog.showModal();
});

// Close the popup
document.querySelector("#close-compare")
    .addEventListener("click", function() {
        compareDialog.close();
    });

// Search for courses
form.addEventListener("submit", async function(event) {
    event.preventDefault();

    const subject = document.querySelector("#subject").value;
    const number = document.querySelector("#number").value.trim();

    message.textContent = "Loading...";
    results.replaceChildren();

    selected.clear();
    updateSelection();

    try {
        const response = await fetch(
            `/courses/${encodeURIComponent(subject)}/${encodeURIComponent(number)}`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Search failed");
        }

        currentCourse = data.course;

        message.textContent =
            `${data.course} - ${data.section_count} sections`;

        for (const section of data.sections) {
            const row = document.createElement("tr");

            // First column: comparison checkbox
            const checkCell = document.createElement("td");
            const checkbox = document.createElement("input");

            checkbox.type = "checkbox";
            checkbox.className = "compare-checkbox";
            checkbox.setAttribute(
                "aria-label",
                `Compare Section ${section.section}`
            );

            checkbox.addEventListener("change", function() {
                if (checkbox.checked) {
                    selected.set(section.section, section);
                } else {
                    selected.delete(section.section);
                }

                updateSelection();
            });

            checkCell.appendChild(checkbox);
            row.appendChild(checkCell);

            // Regular table columns
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

            // Grade Distribution column
            const gradeCell = document.createElement("td");
            gradeCell.appendChild(createGradeBar(section));
            row.appendChild(gradeCell);

            results.appendChild(row);
        }

    } catch (error) {
        message.textContent = error.message;
    }
});
