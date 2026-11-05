
const form = document.querySelector("#search-form");
const message = document.querySelector("#message");
const results = document.querySelector("#results");

const compareButton = document.querySelector("#compare-button");
const selectionCount = document.querySelector("#selection-count");
const compareDialog = document.querySelector("#compare-dialog");

const selected = new Map();
let currentCourse = "";
let currentTerm = "";
let requestGeneration = 0;
let activeController = null;

// Calculate a percentage
function percent(part, total) {
    if (total === 0) return "N/A";
    return `${(part / total * 100).toFixed(1)}%`;
}

// Format API values for display without replacing the original reported GPA.
function formatGpa(value) {
    if (value == null || !Number.isFinite(value)) return "N/A";
    return value.toFixed(3);
}

function discrepancyLabel(section) {
    if (section.gpa_difference == null) return "N/A";
    return section.gpa_discrepancy ? "Difference flagged" : "No difference flagged";
}

// Display confirmation scope without changing or hiding the published source name.
function instructorLabel(section) {
    if (section.instructor_review_evidence !== "user_confirmed") return section.instructor_as_reported;
    const scope = section.instructor_review_scope === "initial_only" ? ", initial only" : "";
    return `${section.instructor_display_name} (user-confirmed${scope}; original: ${section.instructor_as_reported})`;
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
        `${currentCourse} · ${currentTerm}`;

    document.querySelector("#compare-left-title").textContent =
        `${left.college} · Section ${left.section}`;

    document.querySelector("#compare-right-title").textContent =
        `${right.college} · Section ${right.section}`;

    const body = document.querySelector("#compare-results");
    body.replaceChildren();

    addCompareRow(
        "Instructor",
        instructorLabel(left),
        instructorLabel(right)
    );

    addCompareRow(
        "MaroonWay GPA (A-F based)",
        formatGpa(left.gpa_calculated),
        formatGpa(right.gpa_calculated)
    );

    addCompareRow(
        "TAMU Reported GPA",
        formatGpa(left.gpa_reported),
        formatGpa(right.gpa_reported)
    );

    addCompareRow(
        "Absolute GPA Difference",
        formatGpa(left.gpa_difference),
        formatGpa(right.gpa_difference)
    );

    addCompareRow(
        "GPA Discrepancy",
        discrepancyLabel(left),
        discrepancyLabel(right)
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

    const generation = ++requestGeneration;
    activeController?.abort();
    const controller = new AbortController();
    activeController = controller;
    compareDialog.close();
    currentCourse = "";
    currentTerm = "";
    const term = document.querySelector("#term").value;
    const subject = document.querySelector("#subject").value.trim().toUpperCase();
    const number = document.querySelector("#number").value.trim();

    message.textContent = "Loading...";
    results.replaceChildren();

    selected.clear();
    updateSelection();

    try {
        const response = await fetch(
            `/courses/${encodeURIComponent(subject)}/${encodeURIComponent(number)}?term=${encodeURIComponent(term)}`,
            { signal: controller.signal }
        );

        const data = await response.json();
        if (generation !== requestGeneration) return;

        if (!response.ok) {
            throw new Error(data.detail || "Search failed");
        }

        currentCourse = data.course;
        currentTerm = data.term;

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
                    selected.set(`${section.college}:${section.section}`, section);
                } else {
                    selected.delete(`${section.college}:${section.section}`);
                }

                updateSelection();
            });

            checkCell.appendChild(checkbox);
            row.appendChild(checkCell);

            // Regular table columns
            const values = [
                `${section.college} · ${section.section}`,
                instructorLabel(section),
                formatGpa(section.gpa_calculated),
                formatGpa(section.gpa_reported),
                formatGpa(section.gpa_difference),
                discrepancyLabel(section),
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
        if (generation !== requestGeneration || error.name === "AbortError") return;
        message.textContent = error.message;
    }
});
