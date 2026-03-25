import React, { useEffect, useState } from "react";

function App() {
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Use Docker Compose service name 'backend' for cross-container communication
    fetch("http://backend:8000/courses")
      .then(res => {
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        return res.json();
      })
      .then(data => setCourses(data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ padding: 20 }}>Loading courses...</div>;
  if (error) return <div style={{ padding: 20, color: "red" }}>Error: {error}</div>;

  return (
    <div style={{ padding: 20 }}>
      <h1>🌟 Kids Courses</h1>
      {courses.length === 0 && <div>No courses found.</div>}
      {courses.map((c, i) => (
        <div key={i} style={{ marginBottom: 10 }}>
          <a href={c.link} target="_blank" rel="noopener noreferrer">
            {c.title}
          </a>{" "}
          <span style={{ color: "gray" }}>({c.category})</span>
        </div>
      ))}
    </div>
  );
}

export default App;
