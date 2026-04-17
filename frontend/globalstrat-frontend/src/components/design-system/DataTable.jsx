import React from 'react';

function DataTable({ columns, data, highlightRow = null, compact = false, stickyHeader = false }) {
  return (
    <div className={`ds-data-table-wrapper ${stickyHeader ? 'sticky-header' : ''}`}>
      <table className={`ds-data-table ${compact ? 'compact' : ''}`}>
        <thead>
          <tr>
            {columns.map(col => (
              <th
                key={col.key}
                className={col.align === 'right' ? 'text-right' : ''}
                style={{ width: col.width || 'auto' }}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={row._key || i} className={highlightRow === i ? 'highlight-row' : ''}>
              {columns.map(col => (
                <td key={col.key} className={col.align === 'right' ? 'text-right' : ''}>
                  {col.render ? col.render(row[col.key], row, i) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default DataTable;
