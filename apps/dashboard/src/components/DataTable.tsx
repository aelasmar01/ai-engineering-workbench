export function DataTable({
  columns,
  rows,
  title
}: {
  columns: string[];
  rows: string[][];
  title?: string;
}) {
  return (
    <section className="panel">
      {title ? <h2>{title}</h2> : null}
      {rows.length === 0 ? (
        <p className="muted">No records</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column} scope="col">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function EmptyTable({ title }: { title: string }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      <p className="muted">No records</p>
    </section>
  );
}
