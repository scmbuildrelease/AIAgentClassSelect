import React, { useEffect, useState } from "react";

function App() {
  const [courses, setCourses] = useState([]);

  useEffect(() => {
    fetch("http://localhost:8000/courses")
      .then(res => res.json())
      .then(setCourses);
  }, []);

  return (
    <div style={{ padding: 20 }}>
      <h1>🌟 Kids Courses</h1>

      {courses.map((c, i) => (
        <div key={i}>
          <a href={c.link}>{c.title}</a> ({c.category})
        </div>
      ))}
    </div>
  );
}

export default App;
