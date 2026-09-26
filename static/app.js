// =============================
// GRIVON - FRONTEND LOGIC
// =============================


// -----------------------------
// IMAGE PREVIEW
// -----------------------------

const form = document.getElementById("issueForm");
const imageInput = document.getElementById("image");
const preview = document.getElementById("preview");


if (imageInput) {

    imageInput.addEventListener("change", function () {

        const file = imageInput.files[0];

        if (!file) {
            preview.innerHTML = "";
            return;
        }

        const imageURL = URL.createObjectURL(file);

        preview.innerHTML = `
            <img
                src="${imageURL}"
                alt="Selected evidence"
            >
        `;
    });
}


// -----------------------------
// SECURITY HELPER
// -----------------------------

function escapeHTML(value) {

    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


// -----------------------------
// TOAST MESSAGE
// -----------------------------

function showToast(message) {

    const toast = document.getElementById("toast");

    toast.textContent = message;

    toast.classList.add("show");

    setTimeout(() => {

        toast.classList.remove("show");

    }, 2400);
}


// -----------------------------
// SUBMIT ISSUE
// -----------------------------

form.addEventListener("submit", async function (event) {

    event.preventDefault();

    const button =
        form.querySelector("button");

    button.disabled = true;
    button.textContent = "Analysing...";


    try {

        const formData =
            new FormData(form);


        const response =
            await fetch(
                "/api/issues",
                {
                    method: "POST",
                    body: formData
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            showToast(
                data.error ||
                "Submission failed."
            );

            return;
        }


        const issue =
            data.issue;


        showToast(
            `Submitted • ${issue.priority} • Severity ${issue.severity}/100`
        );


        form.reset();

        preview.innerHTML = "";


        await refresh();


        document
            .getElementById("signals")
            .scrollIntoView({
                behavior: "smooth"
            });


    } catch (error) {

        console.error(error);

        showToast(
            "Server connection failed."
        );

    } finally {

        button.disabled = false;

        button.textContent =
            "Run triage →";
    }

});


// -----------------------------
// LOAD MAIN STATISTICS
// -----------------------------

async function loadStats() {

    try {

        const response =
            await fetch("/api/stats");

        const data =
            await response.json();


        document.getElementById("total")
            .textContent = data.total;

        document.getElementById("high")
            .textContent = data.high;

        document.getElementById("progress")
            .textContent = data.progress;

        document.getElementById("resolved")
            .textContent = data.resolved;

        document.getElementById("points")
            .textContent = data.points;


        // Hero cards

        document.getElementById("heroQueue")
            .textContent =
            data.total - data.resolved;

        document.getElementById("heroPoints")
            .textContent =
            data.points;


    } catch (error) {

        console.error(
            "Stats error:",
            error
        );
    }
}


// -----------------------------
// LOAD ISSUE BOARD
// -----------------------------

async function loadIssues() {

    const query =
        new URLSearchParams();


    const status =
        document
            .getElementById("statusFilter")
            .value;


    const category =
        document
            .getElementById("categoryFilter")
            .value;


    const priority =
        document
            .getElementById("priorityFilter")
            .value;


    if (status) {
        query.set("status", status);
    }

    if (category) {
        query.set("category", category);
    }

    if (priority) {
        query.set("priority", priority);
    }


    try {

        const response =
            await fetch(
                "/api/issues?" +
                query.toString()
            );


        const issues =
            await response.json();


        const grid =
            document.getElementById(
                "issueGrid"
            );


        if (!issues.length) {

            grid.innerHTML = `
                <div class="empty">

                    <h3>
                        No issues found
                    </h3>

                    <p>
                        Try another filter
                        or submit a report.
                    </p>

                </div>
            `;

            return;
        }


        grid.innerHTML =
            issues
                .map(createIssueCard)
                .join("");


    } catch (error) {

        console.error(
            "Issue loading error:",
            error
        );
    }
}


// -----------------------------
// CREATE ISSUE CARD
// -----------------------------

function createIssueCard(issue) {

    const severity =
        Number(issue.severity || 0);


    const priority =
        (
            issue.priority ||
            "Low"
        ).toLowerCase();


    let pointsHTML = "";


    if (
        Number(issue.points_awarded) > 0
    ) {

        pointsHTML = `
            <div class="points">

                🏆 +
                ${issue.points_awarded}
                points awarded

            </div>
        `;
    }


    return `

        <article class="issue">


            ${
                issue.image_url
                ?
                `
                    <img
                        class="photo"
                        src="${issue.image_url}"
                        alt="Issue evidence"
                    >
                `
                :
                ""
            }


            <button
                class="delete"
                onclick="deleteIssue(${issue.id})"
                title="Delete report"
            >
                ×
            </button>


            <div class="body">


                <div class="top">

                    <h3>
                        ${escapeHTML(issue.title)}
                    </h3>


                    <span
                        class="tag ${priority}"
                    >
                        ${escapeHTML(issue.priority)}
                    </span>

                </div>


                <p>
                    ${escapeHTML(
                        issue.description
                    )}
                </p>


                <div class="loc">

                    ⌖
                    ${escapeHTML(
                        issue.location
                    )}

                </div>


                <div class="tags">

                    <span class="tag">

                        ${escapeHTML(
                            issue.category
                        )}

                    </span>


                    <span class="tag">

                        ID #${issue.id}

                    </span>

                </div>


                <!-- AI SEVERITY -->

                <div class="severity">

                    <div>

                        <span>
                            AI SEVERITY
                        </span>

                        <b>
                            ${severity}/100
                        </b>

                    </div>


                    <i
                        style="
                            width:${severity}%;
                        "
                    ></i>


                    <small>

                        ${escapeHTML(
                            issue.severity_reason ||
                            "AI severity estimate"
                        )}

                    </small>

                </div>


                <!-- STATUS -->

                <select
                    class="status"
                    onchange="
                        updateStatus(
                            ${issue.id},
                            this.value
                        )
                    "
                >

                    <option
                        ${
                            issue.status === "Reported"
                            ? "selected"
                            : ""
                        }
                    >
                        Reported
                    </option>


                    <option
                        ${
                            issue.status === "In Progress"
                            ? "selected"
                            : ""
                        }
                    >
                        In Progress
                    </option>


                    <option
                        ${
                            issue.status === "Resolved"
                            ? "selected"
                            : ""
                        }
                    >
                        Resolved
                    </option>

                </select>


                ${pointsHTML}

            </div>

        </article>

    `;
}


// -----------------------------
// UPDATE STATUS
// -----------------------------

async function updateStatus(
    issueID,
    newStatus
) {

    try {

        const response =
            await fetch(
                `/api/issues/${issueID}/status`,
                {
                    method: "PATCH",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        status: newStatus
                    })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            showToast(
                data.error ||
                "Update failed."
            );

            return;
        }


        if (data.points_awarded) {

            showToast(
                `Resolved! 🏆 +${data.points_awarded} points`
            );

        } else {

            showToast(
                "Status updated."
            );
        }


        await refresh();


    } catch (error) {

        console.error(error);

        showToast(
            "Could not update status."
        );
    }
}


// -----------------------------
// DELETE ISSUE
// -----------------------------

async function deleteIssue(issueID) {

    const confirmed =
        confirm(
            "Delete this report?"
        );


    if (!confirmed) {
        return;
    }


    try {

        const response =
            await fetch(
                `/api/issues/${issueID}`,
                {
                    method: "DELETE"
                }
            );


        if (!response.ok) {

            showToast(
                "Delete failed."
            );

            return;
        }


        showToast(
            "Issue deleted."
        );


        await refresh();


    } catch (error) {

        console.error(error);

        showToast(
            "Delete failed."
        );
    }
}


// -----------------------------
// ADMIN / CONTROL ROOM
// -----------------------------

async function loadAdmin() {

    try {

        const response =
            await fetch("/api/admin");


        const data =
            await response.json();


        document.getElementById(
            "adminTotal"
        ).textContent = data.total;


        document.getElementById(
            "adminHigh"
        ).textContent = data.high;


        document.getElementById(
            "adminProgress"
        ).textContent = data.progress;


        document.getElementById(
            "adminResolved"
        ).textContent = data.resolved;


        document.getElementById(
            "adminPoints"
        ).textContent = data.points;


        // -------------------------
        // CATEGORY ANALYTICS
        // -------------------------

        const categoryContainer =
            document.getElementById(
                "categoryStats"
            );


        const total =
            data.categories.reduce(
                (sum, item) =>
                    sum + item.count,
                0
            );


        categoryContainer.innerHTML =
            data.categories
                .map(item => {

                    const percentage =
                        total
                        ? (
                            item.count /
                            total
                        ) * 100
                        : 0;


                    return `

                        <div class="cat">

                            <div>

                                <span>
                                    ${escapeHTML(
                                        item.category
                                    )}
                                </span>

                                <b>
                                    ${item.count}
                                </b>

                            </div>


                            <i
                                style="
                                    width:${percentage}%;
                                "
                            ></i>

                        </div>

                    `;

                })
                .join("");


        // -------------------------
        // RECENT ACTIVITY
        // -------------------------

        const activity =
            document.getElementById(
                "recentActivity"
            );


        activity.innerHTML =
            data.recent
                .map(item => {

                    return `

                        <div class="activity">

                            <div>

                                <b>
                                    ${escapeHTML(
                                        item.title
                                    )}
                                </b>

                                <small>

                                    ${escapeHTML(
                                        item.category
                                    )}

                                    •

                                    ${escapeHTML(
                                        item.status
                                    )}

                                </small>

                            </div>


                            <strong>

                                ${item.severity}/100

                            </strong>

                        </div>

                    `;

                })
                .join("");


    } catch (error) {

        console.error(
            "Admin error:",
            error
        );
    }
}


// -----------------------------
// REFRESH EVERYTHING
// -----------------------------

async function refresh() {

    await Promise.all([

        loadStats(),

        loadIssues(),

        loadAdmin()

    ]);
}


// -----------------------------
// FILTER EVENTS
// -----------------------------

[
    "status",
    "category",
    "priority"

].forEach(filter => {

    document
        .getElementById(
            filter + "Filter"
        )
        .addEventListener(
            "change",
            loadIssues
        );

});


// -----------------------------
// START APPLICATION
// -----------------------------

refresh()