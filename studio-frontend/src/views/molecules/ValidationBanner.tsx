import type { ValidationReportResponse } from '@/models';
import { cn } from '@/utils';

export interface ValidationBannerProps {
    report: ValidationReportResponse;
}

export const ValidationBanner = ({ report }: ValidationBannerProps) => (
    <div
        className={cn(
            'rounded-lg border p-3 text-sm',
            report.ok
                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200'
                : 'border-rose-500/40 bg-rose-500/10 text-rose-900 dark:text-rose-200',
        )}
    >
        <p className="font-semibold">
            {report.ok ? 'Validation gates passed' : 'Validation gates failed'}
        </p>
        <p className="mt-1 text-xs opacity-80">
            intent tests: {report.tests_passed ? 'pass' : 'FAIL'} · link check:{' '}
            {report.links_ok ? 'pass' : 'FAIL'}
        </p>
        {!report.ok && (
            <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap font-mono text-[11px] opacity-90">
                {report.tests_passed ? report.links_output : report.tests_output}
            </pre>
        )}
    </div>
);
