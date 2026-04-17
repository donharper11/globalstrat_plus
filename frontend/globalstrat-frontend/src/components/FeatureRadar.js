import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Legend,
} from 'recharts';

const FeatureRadar = ({ features, ceilings, maxValue = 10, size = 250 }) => {
  const { t } = useTranslation();

  if (!features || features.length === 0) return null;

  const data = features.map(f => {
    const ceiling = ceilings?.find(c => c.feature_id === f.feature_id || c.code === f.code);
    return {
      feature: f.feature_name || f.name || f.code,
      level: Number(f.current_level ?? f.level ?? 0),
      ceiling: ceiling ? Number(ceiling.ceiling_value ?? ceiling.ceiling ?? maxValue) : maxValue,
    };
  });

  return (
    <ResponsiveContainer width="100%" height={size}>
      <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
        <PolarGrid />
        <PolarAngleAxis dataKey="feature" tick={{ fontSize: 10 }} />
        <PolarRadiusAxis domain={[0, maxValue]} tick={{ fontSize: 9 }} />
        <Radar
          name={t('rd.ceiling')}
          dataKey="ceiling"
          stroke="#E2E8F0"
          fill="transparent"
          strokeDasharray="4 4"
        />
        <Radar
          name={t('rd.current')}
          dataKey="level"
          stroke="#1E40AF"
          fill="#1E40AF"
          fillOpacity={0.25}
        />
        <Legend wrapperStyle={{ fontSize: 11 }} />
      </RadarChart>
    </ResponsiveContainer>
  );
};

export default FeatureRadar;
