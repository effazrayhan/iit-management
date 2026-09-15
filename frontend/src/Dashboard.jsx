import { useEffect, useState } from "react";

const API = import.meta.env.VITE_API_URL;

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(options.body && { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed");
  return data;
}

function values(form) {
  return Object.fromEntries([...new FormData(form)].filter(([, value]) => value !== ""));
}

export default function Dashboard({ user, notify }) {
  const [data, setData] = useState({ academics: {}, classrooms: [], elections: [], complaints: [], positions: [] });
  const admin = ["SUPER_ADMIN", "DEPARTMENT_ADMIN"].includes(user.role);

  async function refresh() {
    try {
      const [academics, classrooms, elections, complaints, positions, metrics, notifications] = await Promise.all([
        request("/api/academics"), request("/api/classrooms"), request("/api/elections"),
        request("/api/complaints"), request("/api/cr-positions"), request("/api/dashboard"),
        request("/api/notifications"),
      ]);
      const extra = user.role === "STUDENT"
        ? { profile: await request("/api/student/profile"), attendance: await request("/api/student/attendance") }
        : admin ? {
          teachers: await request("/api/admin/teachers"),
          audit: await request("/api/admin/audit"),
        } : {};
      setData({ academics, classrooms, elections, complaints, positions, metrics, notifications, ...extra });
    } catch (error) {
      notify(error.message);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function submit(event, path, method = "POST", transform = values) {
    event.preventDefault();
    try {
      await request(path, { method, body: JSON.stringify(transform(event.currentTarget)) });
      event.currentTarget.reset();
      notify("Saved.");
      await refresh();
    } catch (error) {
      notify(error.message);
    }
  }

  const screen = admin
    ? <Admin data={data} submit={submit} refresh={refresh} notify={notify} />
    : user.role === "TEACHER"
      ? <Teacher data={data} submit={submit} notify={notify} />
      : <Student data={data} submit={submit} refresh={refresh} notify={notify} />;
  return <>
    <div id="overview" className="metrics">{Object.entries(data.metrics || {}).map(([key, value]) => <div key={key}><span className="metric-icon" aria-hidden="true">{key.includes("student") ? "◉" : key.includes("teacher") ? "◇" : key.includes("complaint") ? "!" : "↗"}</span><strong>{value}</strong><small>{key.replaceAll("_", " ")}</small></div>)}</div>
    {data.notifications?.length > 0 && <div id="notifications" className="panel notices"><div className="panel-heading"><span><small>Updates</small><h3>Notifications</h3></span><span className="count-badge">{data.notifications.length}</span></div>{data.notifications.map((item) => <button className={item.read ? "read" : ""} key={item.id} onClick={async () => { await request(`/api/notifications/${item.id}/read`, { method: "PATCH" }); await refresh(); }}><span className="notice-dot" /><span><strong>{item.title}</strong><small>{item.message}</small></span></button>)}</div>}
    <div id="workspace">{screen}</div>
  </>;
}

function Admin({ data, submit, refresh, notify }) {
  const nextStatus = { SUBMITTED: "ACKNOWLEDGED", ACKNOWLEDGED: "UNDER_REVIEW", UNDER_REVIEW: "ASSIGNED", ASSIGNED: "ACTION_TAKEN", ACTION_TAKEN: "RESOLVED" };
  async function action(path, body) {
    try {
      await request(path, { method: "PATCH", body: JSON.stringify(body) });
      await refresh();
    } catch (error) { notify(error.message); }
  }

  return <div className="workspace">
    <div className="grid">
      <div className="panel">
        <h3>Academic setup</h3>
        <form onSubmit={(event) => submit(event, "/api/admin/academic-setup")}>
          <input name="program_code" placeholder="Program code (BSSE)" required />
          <input name="program_name" placeholder="Program name" required />
          <input name="academic_session" placeholder="Session (2022-23)" required />
          <input name="batch_code" placeholder="Batch code (15)" required />
          <input name="batch_name" placeholder="Batch name" required />
          <input name="semester_number" type="number" min="1" max="20" placeholder="Semester number" required />
          <input name="semester_name" placeholder="Semester name" required />
          <input name="course_code" placeholder="Course code" required />
          <input name="course_name" placeholder="Course name" required />
          <input name="credits" type="number" min="1" max="10" placeholder="Credits" required />
          <input name="hall_name" placeholder="Hall (optional)" />
          <button>Save academic data</button>
        </form>
      </div>
      <div className="panel">
        <h3>Teacher requests</h3>
        {data.teachers?.length ? data.teachers.map((teacher) => <article key={teacher.id}>
          <span><strong>{teacher.name}</strong><small>{teacher.email}</small></span>
          <button onClick={() => action(`/api/admin/teachers/${teacher.id}`, { action: "APPROVE" })}>Approve</button>
          <button className="secondary" onClick={() => action(`/api/admin/teachers/${teacher.id}`, { action: "MAKE_ADMIN" })}>Make admin</button>
          <button className="reject" onClick={() => action(`/api/admin/teachers/${teacher.id}`, { action: "REJECT" })}>Reject</button>
        </article>) : <p>No pending requests.</p>}
      </div>
      <div className="panel">
        <h3>CR position</h3>
        <form onSubmit={(event) => submit(event, "/api/admin/cr-positions")}>
          <select name="batch_id" required><option value="">Batch</option>{data.academics.batches?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
          <input name="title" placeholder="General CR" required />
          <input name="seats" type="number" min="1" max="10" defaultValue="1" required />
          <button>Create position</button>
        </form>
      </div>
      <div className="panel">
        <h3>CR election</h3>
        <form onSubmit={(event) => submit(event, "/api/admin/elections")}>
          <select name="position_id" required><option value="">Position</option>{data.positions.map((x) => <option key={x.id} value={x.id}>{x.title}</option>)}</select>
          <input name="title" placeholder="Election title" required />
          {[["nomination_start", "Nomination starts"], ["nomination_end", "Nomination ends"], ["voting_start", "Voting starts"], ["voting_end", "Voting ends"]].map(([name, label]) => <label key={name}>{label}<input name={name} type="datetime-local" required /></label>)}
          <button>Create election</button>
        </form>
      </div>
    </div>
    <div className="panel">
      <h3>Elections and candidates</h3>
      {data.elections.map((election) => <article key={election.id}>
        <span><strong>{election.title}</strong><small>{election.position} · {election.status}</small></span>
        {election.candidates.filter((x) => x.status === "PENDING").map((candidate) => <span key={candidate.id}>
          {candidate.name} <button onClick={() => action(`/api/admin/candidates/${candidate.id}`, { action: "APPROVE" })}>Approve</button>
          <button className="reject" onClick={() => action(`/api/admin/candidates/${candidate.id}`, { action: "REJECT" })}>Reject</button>
        </span>)}
        <button onClick={async () => { try { await request(`/api/admin/elections/${election.id}/close`, { method: "POST" }); await refresh(); } catch (error) { notify(error.message); } }}>Close</button>
      </article>)}
    </div>
    <div className="panel">
      <h3>Complaints</h3>
      {data.complaints.map((item) => <article key={item.id}>
        <span><strong>{item.subject}</strong><small>{item.category} · {item.status} · {item.submitter?.email}</small></span>
        {nextStatus[item.status] && <button onClick={() => action(`/api/admin/complaints/${item.id}`, { status: nextStatus[item.status] })}>{nextStatus[item.status].replaceAll("_", " ")}</button>}
      </article>)}
    </div>
    <div className="panel">
      <h3>Recent audit log</h3>
      {data.audit?.map((item) => <p key={item.id}><strong>{item.action}</strong> {item.entity} #{item.entity_id}<br /><small>{item.actor} · {item.details}</small></p>)}
    </div>
  </div>;
}

function Teacher({ data, submit, notify }) {
  return <div className="workspace">
    <div className="panel">
      <h3>Create classroom</h3>
      <form className="row-form" onSubmit={(event) => submit(event, "/api/classrooms")}>
        <select name="course_id" required><option value="">Course</option>{data.academics.courses?.map((x) => <option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select>
        <select name="batch_id" required><option value="">Batch</option>{data.academics.batches?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
        <select name="semester_id" required><option value="">Semester</option>{data.academics.semesters?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
        <select name="session_id" required><option value="">Session</option>{data.academics.sessions?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
        <input name="section" defaultValue="A" placeholder="Section" required />
        <button>Create</button>
      </form>
    </div>
    {data.classrooms.map((classroom) => <TeacherClassroom key={classroom.id} classroom={classroom} notify={notify} />)}
  </div>;
}

function TeacherClassroom({ classroom, notify }) {
  const [details, setDetails] = useState({ sessions: [], roster: [] });
  const [feedback, setFeedback] = useState(null);
  async function load() { setDetails(await request(`/api/classrooms/${classroom.id}/sessions`)); }
  useEffect(() => { load(); }, []);

  async function addSession(event) {
    event.preventDefault();
    try {
      await request(`/api/classrooms/${classroom.id}/sessions`, { method: "POST", body: JSON.stringify(values(event.currentTarget)) });
      event.currentTarget.reset(); await load();
    } catch (error) { notify(error.message); }
  }

  async function attendance(event, sessionId) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const records = details.roster.map(({ id }) => ({ student_id: id, status: form.get(String(id)) }));
    try {
      await request(`/api/sessions/${sessionId}/attendance`, { method: "PUT", body: JSON.stringify({ records }) });
      notify("Attendance saved."); await load();
    } catch (error) { notify(error.message); }
  }

  return <div className="panel">
    <h3>{classroom.course_code} — {classroom.course_name}</h3>
    <p>{classroom.batch_name} · Section {classroom.section}</p>
    <form className="row-form" onSubmit={addSession}>
      <input name="session_date" type="date" required />
      <input name="starts_at" type="time" required />
      <input name="ends_at" type="time" required />
      <input name="topic" placeholder="Topic" />
      <button>Add class</button>
    </form>
    {details.sessions.map((session) => <form className="attendance" key={session.id} onSubmit={(event) => attendance(event, session.id)}>
      <strong>{session.date} · {session.topic}</strong>
      {details.roster.map((student) => <label key={student.id}>{student.name}<select name={student.id} defaultValue={session.attendance.find((x) => x.student_id === student.id)?.status || "PRESENT"}>{["PRESENT", "ABSENT", "LATE", "EXCUSED"].map((x) => <option key={x}>{x}</option>)}</select></label>)}
      <button>Save attendance</button>
    </form>)}
    <button className="secondary" onClick={async () => { try { setFeedback(await request(`/api/classrooms/${classroom.id}/feedback`)); } catch (error) { notify(error.message); } }}>View feedback</button>
    {feedback && <p>{feedback.responses} responses · Clarity {feedback.ratings.clarity}/5 · {feedback.comments.join(" · ")}</p>}
  </div>;
}

function Student({ data, submit, refresh, notify }) {
  const profile = data.profile || {};
  async function electionAction(path, body = {}) {
    try { await request(path, { method: "POST", body: JSON.stringify(body) }); await refresh(); }
    catch (error) { notify(error.message); }
  }

  return <div className="workspace">
    <div className="grid">
      <div className="panel">
        <h3>My profile</h3>
        <p>{profile.program} · Batch {profile.batch} · Roll {profile.roll}</p>
        <form onSubmit={(event) => submit(event, "/api/student/profile", "PUT", (form) => ({ ...values(form), donor_available: form.elements.donor_available.checked, donor_contact_visible: form.elements.donor_contact_visible.checked }))}>
          <input name="phone" defaultValue={profile.phone} placeholder="Phone" required />
          <select name="hall_id" defaultValue={profile.hall_id || ""}><option value="">Hall</option>{data.academics.halls?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
          <input name="hometown_district" defaultValue={profile.hometown_district} placeholder="Hometown district" />
          <textarea name="current_address" defaultValue={profile.current_address} placeholder="Current address" required />
          <select name="blood_group" defaultValue={profile.blood_group || ""}><option value="">Blood group</option>{["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map((x) => <option key={x}>{x}</option>)}</select>
          <input name="last_blood_donation" type="date" defaultValue={profile.last_blood_donation || ""} />
          <label className="check"><input name="donor_available" type="checkbox" defaultChecked={profile.donor_available} /> Available as blood donor</label>
          <label className="check"><input name="donor_contact_visible" type="checkbox" defaultChecked={profile.donor_contact_visible} /> Show my phone to signed-in users</label>
          <button>Save profile</button>
        </form>
      </div>
      <div className="panel">
        <h3>Attendance</h3>
        {data.attendance?.map((item) => <p key={item.classroom_id}><strong>{item.course}</strong><br />{item.percentage}% · {item.present} present · {item.absent} absent</p>)}
      </div>
    </div>
    <div className="panel">
      <h3>CR elections</h3>
      {data.elections.map((election) => <div className="election" key={election.id}>
        <strong>{election.title}</strong><small>{election.position}</small>
        <button className="secondary" onClick={() => electionAction(`/api/elections/${election.id}/nominate`, { manifesto: "" })}>Nominate myself</button>
        {election.candidates.filter((x) => x.status === "APPROVED").map((candidate) => <button key={candidate.id} disabled={election.has_voted} onClick={() => electionAction(`/api/elections/${election.id}/vote`, { candidate_id: candidate.id })}>Vote for {candidate.name}</button>)}
      </div>)}
    </div>
    <div className="panel">
      <h3>Course feedback</h3>
      {data.classrooms.map((classroom) => <form className="feedback" key={classroom.id} onSubmit={(event) => submit(event, `/api/classrooms/${classroom.id}/feedback`)}>
        <strong>{classroom.course_code} — {classroom.course_name}</strong>
        {[["clarity", "Clarity"], ["organization", "Organization"], ["fairness", "Fairness"], ["regularity", "Regularity"], ["interaction", "Interaction"]].map(([name, label]) => <label key={name}>{label}<input name={name} type="number" min="1" max="5" defaultValue="5" required /></label>)}
        <textarea name="comment" placeholder="Suggestion (optional)" />
        <button>Submit anonymously</button>
      </form>)}
    </div>
    <div className="panel">
      <h3>Complaints</h3>
      <form onSubmit={(event) => submit(event, "/api/complaints", "POST", (form) => ({ ...values(form), confidential: form.elements.confidential.checked }))}>
        <select name="category" required>{["ACADEMIC", "CLASSROOM", "LAB", "FACILITIES", "TEACHER", "ADMINISTRATION", "HARASSMENT_SAFETY", "OTHER"].map((x) => <option key={x}>{x}</option>)}</select>
        <input name="subject" placeholder="Subject" required />
        <textarea name="details" placeholder="Describe the issue" minLength="10" required />
        <label className="check"><input name="confidential" type="checkbox" defaultChecked /> Confidential</label>
        <button>Submit complaint</button>
      </form>
      {data.complaints.map((item) => <p key={item.id}><strong>{item.subject}</strong> · {item.status}</p>)}
    </div>
    <DonorSearch batches={data.academics.batches || []} notify={notify} />
  </div>;
}

function DonorSearch({ batches, notify }) {
  const [results, setResults] = useState([]);
  async function search(event) {
    event.preventDefault();
    const query = new URLSearchParams(values(event.currentTarget));
    try { setResults(await request(`/api/donors?${query}`)); }
    catch (error) { notify(error.message); }
  }
  return <div className="panel">
    <h3>Blood donors</h3>
    <form className="row-form" onSubmit={search}>
      <select name="blood_group"><option value="">Any blood group</option>{["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map((x) => <option key={x}>{x}</option>)}</select>
      <select name="batch_id"><option value="">Any batch</option>{batches.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
      <button>Search</button>
    </form>
    {results.map((item, index) => <p key={`${item.name}-${index}`}><strong>{item.name}</strong> · {item.blood_group} · Batch {item.batch}{item.phone && ` · ${item.phone}`}</p>)}
  </div>;
}
