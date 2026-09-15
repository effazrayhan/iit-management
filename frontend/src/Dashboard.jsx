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

export default function Dashboard({ user, page, notify, onUserUpdate }) {
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
          staff: await request("/api/admin/users"),
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

  const notificationList = <Notifications items={data.notifications || []} refresh={refresh} />;
  if (page === "notifications") return <div className="page-view">{notificationList}</div>;
  if (page === "overview") return <div className="page-view">
    <div className="overview-heading"><span><p className="eyebrow">Dashboard</p><h2>Welcome back, {user.name.split(" ")[0]}</h2></span><p>A quick look at your IIT workspace.</p></div>
    <div className="metrics">{Object.entries(data.metrics || {}).map(([key, value]) => <div key={key}><span className="metric-icon" aria-hidden="true">{key.includes("student") ? "◉" : key.includes("teacher") ? "◇" : key.includes("complaint") ? "!" : "↗"}</span><strong>{value}</strong><small>{key.replaceAll("_", " ")}</small></div>)}</div>
    {(data.notifications || []).length > 0 && <div className="overview-notifications">{<Notifications items={data.notifications.slice(0, 4)} refresh={refresh} />}</div>}
  </div>;
  if (admin) return <div className="page-view"><Admin user={user} data={data} submit={submit} refresh={refresh} notify={notify} onUserUpdate={onUserUpdate} /></div>;
  if (user.role === "TEACHER") return <div className="page-view"><Teacher user={user} data={data} submit={submit} notify={notify} onUserUpdate={onUserUpdate} /></div>;
  return <div className="page-view"><Student user={user} page={page} data={data} submit={submit} refresh={refresh} notify={notify} onUserUpdate={onUserUpdate} /></div>;
}

function Notifications({ items, refresh }) {
  return <div className="panel notices"><div className="panel-heading"><span><small>Updates</small><h3>Notifications</h3></span><span className="count-badge">{items.length}</span></div>{items.length ? items.map((item) => <button className={item.read ? "read" : ""} key={item.id} onClick={async () => { await request(`/api/notifications/${item.id}/read`, { method: "PATCH" }); await refresh(); }}><span className="notice-dot" /><span><strong>{item.title}</strong><small>{item.message}</small></span></button>) : <div className="empty-state"><strong>You're all caught up</strong><p>New class and campus updates will appear here.</p></div>}</div>;
}

function ProfilePicture({ user, notify, onUserUpdate }) {
  const [preview, setPreview] = useState(user.profile_picture || "");
  const initials = (user.name || user.email || "U").split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase();
  async function select(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 1500000) { notify("Choose an image under 1.5 MB."); return; }
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const result = await request("/api/profile-picture", { method: "PUT", body: JSON.stringify({ image: reader.result }) });
        setPreview(result.profile_picture || ""); onUserUpdate?.({ profile_picture: result.profile_picture || "" }); notify("Profile picture updated.");
      } catch (error) { notify(error.message); }
    };
    reader.readAsDataURL(file);
  }
  async function remove() {
    try { await request("/api/profile-picture", { method: "PUT", body: JSON.stringify({ image: null }) }); setPreview(""); onUserUpdate?.({ profile_picture: "" }); notify("Profile picture removed."); }
    catch (error) { notify(error.message); }
  }
  return <div className="panel profile-picture-panel"><div className="profile-picture-preview">{preview ? <img src={preview} alt="Profile" /> : <span>{initials}</span>}</div><div><strong>Profile picture</strong><small>Shown to your classmates and teachers</small><div className="profile-picture-copy"><label className="button secondary">Choose image<input type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={select} /></label>{preview && <button className="secondary" type="button" onClick={remove}>Remove</button>}</div></div></div>;
}

function AttendancePicker({ name, label, defaultValue = "PRESENT" }) {
  const [value, setValue] = useState(defaultValue);
  const statuses = ["PRESENT", "ABSENT", "LATE", "EXCUSED"];
  return <div className="attendance-picker-row"><span>{label}</span><input type="hidden" name={name} value={value} /><div className="attendance-buttons">{statuses.map((status) => <button type="button" key={status} className={value === status ? "selected" : ""} onClick={() => setValue(status)}>{status[0] + status.slice(1).toLowerCase()}</button>)}</div></div>;
}

function StarRating({ name, label, defaultValue = 5 }) {
  const [value, setValue] = useState(defaultValue);
  return <label className="star-rating"><span>{label}</span><span className="stars" aria-label={`${label}: ${value} out of 5`}>{[1, 2, 3, 4, 5].map((star) => <button type="button" key={star} className={star <= value ? "selected" : ""} aria-label={`${star} stars`} onClick={() => setValue(star)}>★</button>)}</span><input type="hidden" name={name} value={value} /></label>;
}

function Admin({ user, data, submit, refresh, notify, onUserUpdate }) {
  const nextStatus = { SUBMITTED: "ACKNOWLEDGED", ACKNOWLEDGED: "UNDER_REVIEW", UNDER_REVIEW: "ASSIGNED", ASSIGNED: "ACTION_TAKEN", ACTION_TAKEN: "RESOLVED" };
  async function action(path, body) {
    try {
      await request(path, { method: "PATCH", body: JSON.stringify(body) });
      await refresh();
    } catch (error) { notify(error.message); }
  }

  return <div className="workspace"><ProfilePicture user={user} notify={notify} onUserUpdate={onUserUpdate} />
    <div className="grid">
      <div className="panel">
        <h3>Academic administration</h3>
        <p className="helper">BSSE batches and sessions are created automatically from student IIT email addresses. Elected CRs maintain batch names, semesters, and course plans.</p>
        <div className="compact-list">{data.academics.batches?.map((batch) => {
          const session = data.academics.sessions?.find((item) => item.id === batch.session_id);
          const semester = data.academics.semesters?.find((item) => item.id === batch.current_semester_id);
          return <p key={batch.id}><strong>{batch.name}</strong><small>BSSE {batch.code} · {session?.name} · {semester ? `Semester ${semester.number}` : "Semester not assigned"}</small></p>;
        })}</div>
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
        <h3>Staff administration</h3>
        {data.staff?.map((member) => <article key={member.id}>
          <span><strong>{member.name}</strong><small>{member.email} · {member.role.replaceAll("_", " ")} · {member.status}</small></span>
          {member.email !== user.email && member.role !== "SUPER_ADMIN" && <>
            {user.role === "SUPER_ADMIN" && <button className="secondary" onClick={() => action(`/api/admin/users/${member.id}`, { action: member.role === "DEPARTMENT_ADMIN" ? "MAKE_TEACHER" : "MAKE_ADMIN" })}>{member.role === "DEPARTMENT_ADMIN" ? "Make teacher" : "Make admin"}</button>}
            <button className={member.status === "ACTIVE" ? "reject" : "secondary"} onClick={() => action(`/api/admin/users/${member.id}`, { action: member.status === "ACTIVE" ? "DEACTIVATE" : "ACTIVATE" })}>{member.status === "ACTIVE" ? "Deactivate" : "Activate"}</button>
          </>}
        </article>)}
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

function Teacher({ user, data, submit, notify, onUserUpdate }) {
  return <div className="workspace"><ProfilePicture user={user} notify={notify} onUserUpdate={onUserUpdate} />
    <div className="panel">
      <h3>Create classroom</h3>
      <form className="row-form" onSubmit={(event) => submit(event, "/api/classrooms")}>
        <select name="course_id" required><option value="">Course</option>{data.academics.courses?.map((x) => <option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select>
        <select name="batch_id" required><option value="">Batch</option>{data.academics.batches?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
        <select name="semester_id" required><option value="">Semester</option>{data.academics.semesters?.map((x) => <option key={x.id} value={x.id}>Semester {x.number}</option>)}</select>
        <select name="session_id" required><option value="">Session</option>{data.academics.sessions?.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
        <input name="section" defaultValue="A" placeholder="Section" required />
        <button>Create</button>
      </form>
    </div>
    {data.classrooms.map((classroom) => <TeacherClassroom key={classroom.id} classroom={classroom} notify={notify} />)}
  </div>;
}

function TeacherClassroom({ classroom, notify }) {
  const [details, setDetails] = useState({ sessions: [], recurring: [], roster: [] });
  const [posts, setPosts] = useState([]);
  const [postKind, setPostKind] = useState("ANNOUNCEMENT");
  const [feedback, setFeedback] = useState(null);
  async function load() {
    const [classDetails, classPosts] = await Promise.all([
      request(`/api/classrooms/${classroom.id}/sessions`),
      request(`/api/classrooms/${classroom.id}/posts`),
    ]);
    setDetails(classDetails);
    setPosts(classPosts);
  }
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

  async function publish(event) {
    event.preventDefault();
    try {
      await request(`/api/classrooms/${classroom.id}/posts`, { method: "POST", body: JSON.stringify(values(event.currentTarget)) });
      event.currentTarget.reset();
      setPostKind("ANNOUNCEMENT");
      notify("Published to the class.");
      await load();
    } catch (error) { notify(error.message); }
  }

  async function recurringAction(path, occurrence_date, reason = "") {
    try {
      await request(path, { method: "POST", body: JSON.stringify({ occurrence_date, reason }) });
      notify(path.endsWith("cancel") ? "Class cancelled and students notified." : "Class opened for attendance.");
      await load();
    } catch (error) { notify(error.message); }
  }

  return <div className="panel class-workspace">
    <div className="class-header"><span className="class-code">{classroom.course_code}</span><span><h3>{classroom.course_name}</h3><small>{classroom.batch_name} · Section {classroom.section} · {details.roster.length} students</small></span></div>
    <h4>Schedule a class</h4>
    <form className="row-form" onSubmit={addSession}>
      <input name="session_date" type="date" required />
      <input name="starts_at" type="time" required />
      <input name="ends_at" type="time" required />
      <input name="topic" placeholder="Topic" />
      <button>Add class</button>
    </form>
    <h4>Recurring schedule</h4>
    <form className="recurring-form" onSubmit={async (event) => {
      event.preventDefault();
      try {
        await request(`/api/classrooms/${classroom.id}/recurring`, { method: "POST", body: JSON.stringify({ ...values(event.currentTarget), weekday: Number(event.currentTarget.elements.weekday.value), reminder_minutes: Number(event.currentTarget.elements.reminder_minutes.value) }) });
        event.currentTarget.reset(); notify("Recurring class scheduled."); await load();
      } catch (error) { notify(error.message); }
    }}>
      <select name="weekday" aria-label="Weekday" required>{["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((day, index) => <option value={index} key={day}>{day}</option>)}</select>
      <input name="starts_at" type="time" aria-label="Start time" required />
      <input name="ends_at" type="time" aria-label="End time" required />
      <input name="topic" placeholder="Topic" />
      <select name="reminder_minutes" aria-label="Reminder"><option value="15">15 min reminder</option><option value="30">30 min reminder</option><option value="60">1 hour reminder</option></select>
      <button>Repeat weekly</button>
    </form>
    <div className="recurring-list">{details.recurring.map((schedule) => <article key={schedule.id}>
      <span><strong>{weekdayName(schedule.weekday)} · {formatTime(schedule.starts_at)}–{formatTime(schedule.ends_at)}</strong><small>Next: {formatDate(schedule.next_date)} · Reminder {schedule.reminder_minutes} min before</small></span>
      <button onClick={() => recurringAction(`/api/recurring-classes/${schedule.id}/start`, schedule.next_date)}>Take attendance</button>
      <button className="reject" onClick={() => recurringAction(`/api/recurring-classes/${schedule.id}/cancel`, schedule.next_date, "Cancelled by teacher")}>Cancel class</button>
    </article>)}</div>
    <h4>Publish to class</h4>
    <form className="post-composer" onSubmit={publish}>
      <select name="kind" value={postKind} onChange={(event) => setPostKind(event.target.value)}><option value="ANNOUNCEMENT">Announcement</option><option value="RESOURCE">Resource</option></select>
      <input name="title" placeholder="Title" required />
      <textarea name="content" placeholder="Message or instructions" />
      {postKind === "RESOURCE" && <input name="resource_url" type="url" placeholder="https://…" required />}
      <button>Publish</button>
    </form>
    <ClassFeed posts={posts} />
    <h4>Attendance sessions</h4>
    {details.sessions.map((session) => session.status === "CANCELLED" ? <div className="cancelled-session" key={session.id}><strong>{formatDate(session.date)} · {session.topic || "Class session"}</strong><span>Cancelled</span></div> : <form className="attendance" key={session.id} onSubmit={(event) => attendance(event, session.id)}>
      <strong>{formatDate(session.date)} · {formatTime(session.starts_at)}–{formatTime(session.ends_at)} · {session.topic || "Class session"}</strong>
      {details.roster.map((student) => <AttendancePicker key={student.id} name={student.id} label={student.name} defaultValue={session.attendance.find((x) => x.student_id === student.id)?.status || "PRESENT"} />)}
      <button>Save attendance</button>
    </form>)}
    <button className="secondary" onClick={async () => { try { setFeedback(await request(`/api/classrooms/${classroom.id}/feedback`)); } catch (error) { notify(error.message); } }}>View feedback</button>
    {feedback && <p>{feedback.responses} responses · Clarity {feedback.ratings.clarity}/5 · {feedback.comments.join(" · ")}</p>}
  </div>;
}

function Student({ user, page, data, submit, refresh, notify, onUserUpdate }) {
  const profile = data.profile || {};
  async function electionAction(path, body = {}) {
    try { await request(path, { method: "POST", body: JSON.stringify(body) }); await refresh(); }
    catch (error) { notify(error.message); }
  }

  const classes = <>
    <section className="hub-section">
      <div className="section-heading"><span><small>Learning</small><h2>My classes</h2></span><span className="count-badge">{data.classrooms.length}</span></div>
      <div className="class-grid">{data.classrooms.length ? data.classrooms.map((classroom) => <StudentClassroom key={classroom.id} classroom={classroom} notify={notify} />) : <div className="panel empty-state"><strong>No classes yet</strong><p>Your enrolled classes will appear here after a teacher creates them.</p></div>}</div>
    </section>
    <div className="panel">
      <h3>Course feedback</h3>
      {data.classrooms.map((classroom) => <form className="feedback" key={classroom.id} onSubmit={(event) => submit(event, `/api/classrooms/${classroom.id}/feedback`)}>
        <strong>{classroom.course_code} — {classroom.course_name}</strong>
        {[["clarity", "Clarity"], ["organization", "Organization"], ["fairness", "Fairness"], ["regularity", "Regularity"], ["interaction", "Interaction"]].map(([name, label]) => <StarRating key={name} name={name} label={label} />)}
        <textarea name="comment" placeholder="Suggestion (optional)" />
        <button>Submit anonymously</button>
      </form>)}
    </div>
  </>;
  if (page === "classes") return <div className="workspace classes-page"><ProfilePicture user={user} notify={notify} onUserUpdate={onUserUpdate} />{classes}</div>;
  if (page === "others") return <StudentOthers data={data} submit={submit} refresh={refresh} notify={notify} />;

  return <div className="workspace student-hub">
    <ProfilePicture user={user} notify={notify} onUserUpdate={onUserUpdate} />
    <div className="hub-hero">
      <div><p className="eyebrow">Student hub</p><h2>{profile.batch_name || `Batch ${profile.batch}`}</h2><p>BSSE · Session {profile.academic_session} · {profile.semester_number ? `Semester ${profile.semester_number}` : "Semester pending"}</p></div>
      <div className="hub-actions"><span>{data.classrooms.length} active classes</span><span>{data.notifications?.filter((item) => !item.read).length || 0} unread updates</span></div>
    </div>
    <div className="grid">
      <div className="panel">
        <h3>My profile</h3>
        <p>{profile.program} · {profile.batch_name || `Batch ${profile.batch}`} · Session {profile.academic_session} · {profile.semester_number ? `Semester ${profile.semester_number}` : "Semester not assigned"} · Roll {profile.roll}</p>
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
      {profile.is_cr && <CRAcademicSetup profile={profile} submit={submit} />}
    </div>
  </div>;
}

function StudentOthers({ data, submit, refresh, notify }) {
  async function electionAction(path, body = {}) {
    try { await request(path, { method: "POST", body: JSON.stringify(body) }); await refresh(); }
    catch (error) { notify(error.message); }
  }
  return <div className="workspace others-page">
    <div className="page-intro"><p className="eyebrow">More campus tools</p><h2>Others</h2><p>Support, elections, and community resources for your batch.</p></div>
    <div className="panel"><h3>CR elections</h3>{data.elections.length ? data.elections.map((election) => <div className="election" key={election.id}>
      <strong>{election.title}</strong><small>{election.position} · {election.status}</small>
      <button className="secondary" onClick={() => electionAction(`/api/elections/${election.id}/nominate`, { manifesto: "" })}>Nominate myself</button>
      {election.candidates.filter((x) => x.status === "APPROVED").map((candidate) => <button key={candidate.id} disabled={election.has_voted} onClick={() => electionAction(`/api/elections/${election.id}/vote`, { candidate_id: candidate.id })}>Vote for {candidate.name}</button>)}
    </div>) : <div className="empty-state"><strong>No elections right now</strong><p>Your batch elections will appear here.</p></div>}</div>
    <div className="panel"><h3>Complaints and support</h3>
      <form onSubmit={(event) => submit(event, "/api/complaints", "POST", (form) => ({ ...values(form), confidential: form.elements.confidential.checked }))}>
        <select name="category" required>{["ACADEMIC", "CLASSROOM", "LAB", "FACILITIES", "TEACHER", "ADMINISTRATION", "HARASSMENT_SAFETY", "OTHER"].map((x) => <option key={x}>{x}</option>)}</select>
        <input name="subject" placeholder="Subject" required /><textarea name="details" placeholder="Describe the issue" minLength="10" required />
        <label className="check"><input name="confidential" type="checkbox" defaultChecked /> Confidential</label><button>Submit complaint</button>
      </form>
      {data.complaints.map((item) => <p key={item.id}><strong>{item.subject}</strong> · {item.status}</p>)}</div>
    <DonorSearch batches={data.academics.batches || []} notify={notify} />
  </div>;
}

function StudentClassroom({ classroom, notify }) {
  const [details, setDetails] = useState({ sessions: [], recurring: [] });
  const [posts, setPosts] = useState([]);
  useEffect(() => {
    Promise.all([
      request(`/api/classrooms/${classroom.id}/sessions`),
      request(`/api/classrooms/${classroom.id}/posts`),
    ]).then(([classDetails, classPosts]) => {
      setDetails(classDetails);
      setPosts(classPosts);
    }).catch((error) => notify(error.message));
  }, [classroom.id]);
  const nextSession = [...details.sessions]
    .filter((session) => session.status !== "CANCELLED" && new Date(`${session.date}T${session.ends_at}`) >= new Date())
    .sort((a, b) => `${a.date}${a.starts_at}`.localeCompare(`${b.date}${b.starts_at}`))[0];
  return <article className="student-class-card">
    <div className="class-header"><span className="class-code">{classroom.course_code}</span><span><h3>{classroom.course_name}</h3><small>{classroom.teacher_name} · Section {classroom.section}</small></span></div>
    <div className="next-class">{nextSession ? <><small>Next class</small><strong>{formatDate(nextSession.date)} at {formatTime(nextSession.starts_at)}</strong><span>{nextSession.topic || "Class session"}</span></> : <><small>Schedule</small><strong>No upcoming class</strong><span>Check back for updates.</span></>}</div>
    {details.recurring?.map((schedule) => <div className="recurring-chip" key={schedule.id}><strong>Every {weekdayName(schedule.weekday)}</strong><span>{formatTime(schedule.starts_at)}–{formatTime(schedule.ends_at)} · next {formatDate(schedule.next_date)}</span></div>)}
    <ClassFeed posts={posts.slice(0, 3)} compact />
  </article>;
}

function ClassFeed({ posts, compact = false }) {
  return <div className={`class-feed ${compact ? "compact" : ""}`}>
    {!compact && <h4>Class feed</h4>}
    {posts.length ? posts.map((post) => <article className="class-post" key={post.id}>
      <span className={`post-kind ${post.kind.toLowerCase()}`}>{post.kind === "RESOURCE" ? "↗" : "•"}</span>
      <span><strong>{post.title}</strong><small>{post.kind.toLowerCase()} · {post.author} · {formatDate(post.created_at)}</small>{post.content && <p>{post.content}</p>}{post.resource_url && <a href={post.resource_url} target="_blank" rel="noreferrer">Open resource</a>}</span>
    </article>) : <p className="empty-copy">No class updates yet.</p>}
  </div>;
}

function formatDate(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(`${value}`.slice(0, 10) + "T00:00:00"));
}

function formatTime(value) {
  if (!value) return "";
  const [hours, minutes] = value.split(":");
  return new Intl.DateTimeFormat("en", { hour: "numeric", minute: "2-digit" }).format(new Date(2000, 0, 1, Number(hours), Number(minutes)));
}

function weekdayName(value) {
  return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][value];
}

function CRAcademicSetup({ profile, submit }) {
  const [courseRows, setCourseRows] = useState([0]);
  function transform(form) {
    const formData = new FormData(form);
    const codes = formData.getAll("course_code");
    const names = formData.getAll("course_name");
    const credits = formData.getAll("credits");
    return {
      batch_name: formData.get("batch_name"),
      semester_number: Number(formData.get("semester_number")),
      courses: codes.map((course_code, index) => ({
        course_code,
        course_name: names[index],
        credits: Number(credits[index]),
      })),
    };
  }
  return <div className="panel cr-academics">
    <div className="panel-heading"><span><small>CR controls</small><h3>Batch academics</h3></span><span className="count-badge">BSSE</span></div>
    <p className="helper">Batch {profile.batch} · Session {profile.academic_session}. These values come from your IIT email and cannot be changed.</p>
    <form onSubmit={(event) => submit(event, "/api/cr/academic-setup", "POST", transform)}>
      <label>Batch name<input name="batch_name" defaultValue={profile.batch_name} placeholder="Choose your batch name" required /></label>
      <label>Current semester<input name="semester_number" type="number" min="1" max="20" defaultValue={profile.semester_number || ""} placeholder="Semester number" required /></label>
      <div className="course-editor">
        <div className="course-editor-heading"><strong>Semester courses</strong><button className="secondary" type="button" onClick={() => setCourseRows((rows) => [...rows, Math.max(...rows) + 1])}>Add course</button></div>
        {courseRows.map((row, index) => <div className="course-row" key={row}>
          <input name="course_code" placeholder="Course code" aria-label={`Course ${index + 1} code`} required />
          <input name="course_name" placeholder="Course name" aria-label={`Course ${index + 1} name`} required />
          <input name="credits" type="number" min="0.5" max="10" step="0.5" placeholder="Credits" aria-label={`Course ${index + 1} credits`} required />
          {courseRows.length > 1 && <button className="remove-row" type="button" aria-label={`Remove course ${index + 1}`} onClick={() => setCourseRows((rows) => rows.filter((item) => item !== row))}>×</button>}
        </div>)}
      </div>
      <button>Save academic plan</button>
    </form>
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
