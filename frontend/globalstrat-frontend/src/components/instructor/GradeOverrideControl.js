import React, { useState } from 'react';
import {
  Button, Input, InputNumber, Modal, Select, Space, Typography, message,
} from 'antd';

import { overrideGrade, clearGradeOverride } from '../../api/instructor';
import { bilingualServerReason } from '../../pages/bilingualServerReason';

const { Paragraph, Text } = Typography;

/**
 * The grading override, on the console (W-CE-12).
 *
 * `POST /grades/override/` and `DELETE /grades/override/` have existed since
 * grading shipped, `api/instructor.js` exported `overrideGrade`, and the
 * TeamGrade row keeps the override, the computed score it replaced, the
 * comment and who graded -- but no screen called any of it, so an instructor
 * who disagreed with one category score had no way to say so except the
 * database. This is one button per team on the Team Grades table: pick the
 * category, write the score and why, and the grades are recalculated so the
 * final column reflects it (calculation keeps overrides).
 */
export default function GradeOverrideControl({
  t, instanceId, teamId, teamName, categories, onChanged,
}) {
  const [open, setOpen] = useState(false);
  const [categoryId, setCategoryId] = useState(categories?.[0]?.category_id ?? null);
  const [score, setScore] = useState(null);
  const [comments, setComments] = useState('');
  const [busy, setBusy] = useState(false);

  const category = (categories || []).find((c) => c.category_id === categoryId) || null;

  const show = () => {
    const first = categories?.[0] || null;
    setCategoryId(first?.category_id ?? null);
    setScore(first ? first.final_score : null);
    setComments(first?.comments || '');
    setOpen(true);
  };

  const choose = (id) => {
    const next = (categories || []).find((c) => c.category_id === id) || null;
    setCategoryId(id);
    setScore(next ? next.final_score : null);
    setComments(next?.comments || '');
  };

  const finish = async (work, done) => {
    setBusy(true);
    try {
      await work();
      message.success(done);
      setOpen(false);
      onChanged?.();
    } catch (err) {
      message.error(bilingualServerReason(err) || t('instructor.grade_override_failed'), 8);
    } finally {
      setBusy(false);
    }
  };

  const canSave = category && Number.isFinite(Number(score)) && score !== null
    && score >= 0 && score <= 100;

  return (
    <>
      <Button size="small" onClick={show} disabled={!categories?.length}>
        {t('instructor.grade_override')}
      </Button>
      <Modal
        title={t('instructor.grade_override_title', { team: teamName })}
        open={open}
        onCancel={() => setOpen(false)}
        confirmLoading={busy}
        okText={t('instructor.grade_override_save')}
        cancelText={t('common.cancel')}
        okButtonProps={{ disabled: !canSave }}
        onOk={() => finish(
          () => overrideGrade(instanceId, teamId, categoryId, Number(score), comments.trim()),
          t('instructor.grade_override_saved', {
            team: teamName, category: category?.category_name,
          }),
        )}
      >
        <Paragraph type="secondary">{t('instructor.grade_override_hint')}</Paragraph>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text strong>{t('instructor.category')}</Text>
            <Select style={{ width: '100%' }} value={categoryId} onChange={choose}
              options={(categories || []).map((c) => ({
                value: c.category_id,
                label: `${c.category_name} (${Number(c.weight).toFixed(0)}%)`,
              }))} />
          </div>
          <div>
            <Text strong>{t('instructor.grade_override_score')}</Text>
            <InputNumber min={0} max={100} step={0.5} value={score}
              onChange={setScore} style={{ width: '100%' }}
              aria-label={t('instructor.grade_override_score')} />
            {category && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('instructor.grade_computed_was', { score: Number(category.computed_score).toFixed(1) })}
              </Text>
            )}
          </div>
          <div>
            <Text strong>{t('instructor.grade_override_comments')}</Text>
            <Input.TextArea rows={3} value={comments}
              onChange={(e) => setComments(e.target.value)}
              aria-label={t('instructor.grade_override_comments')} />
          </div>
          {category && category.override_score !== null && category.override_score !== undefined && (
            <Button danger size="small" loading={busy} onClick={() => finish(
              () => clearGradeOverride(instanceId, teamId, categoryId),
              t('instructor.grade_override_cleared', {
                team: teamName, category: category.category_name,
              }),
            )}>
              {t('instructor.grade_override_clear')}
            </Button>
          )}
        </Space>
      </Modal>
    </>
  );
}
