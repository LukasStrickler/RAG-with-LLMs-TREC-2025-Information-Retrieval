"use client";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";

interface SearchFiltersProps {
    mode: "lexical" | "vector" | "hybrid";
    onModeChange: (mode: "lexical" | "vector" | "hybrid") => void;
    topK: number;
    onTopKChange: (value: number) => void;
}

export function SearchFilters({
    mode,
    onModeChange,
    topK,
    onTopKChange,
}: SearchFiltersProps) {
    return (
        <div className="w-full max-w-3xl space-y-6 bg-card p-6 rounded-lg border shadow-sm">
            <div className="space-y-2">
                <Label className="text-sm font-medium">Search Mode</Label>
                <Tabs value={mode} onValueChange={(v) => onModeChange(v as any)}>
                    <TabsList className="grid w-full grid-cols-3">
                        <TabsTrigger value="lexical">Lexical</TabsTrigger>
                        <TabsTrigger value="vector">Vector</TabsTrigger>
                        <TabsTrigger value="hybrid">Hybrid</TabsTrigger>
                    </TabsList>
                </Tabs>
            </div>

            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <Label className="text-sm font-medium">Results to show</Label>
                    <span className="text-sm font-semibold text-blue-600">{topK}</span>
                </div>
                <Slider
                    value={[topK]}
                    onValueChange={(values) => onTopKChange(values[0])}
                    min={5}
                    max={50}
                    step={5}
                    className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground">
                    <span>5</span>
                    <span>50</span>
                </div>
            </div>
        </div>
    );
}
