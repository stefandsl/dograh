import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

interface WorkflowConfigErrorProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    error: string | null;
    onNavigateToWorkflow: () => void;
}

export const WorkflowConfigErrorDialog = ({
    open,
    onOpenChange,
    error,
    onNavigateToWorkflow
}: WorkflowConfigErrorProps) => {
    const t = useTranslations("components.workflowConfigErrorDialog");
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>{t("title")}</DialogTitle>
                    <DialogDescription className="text-red-500 whitespace-pre-line">
                        {error}
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button onClick={onNavigateToWorkflow}>
                        {t("goToWorkflow")}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
