"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, SlidersHorizontal } from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

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
    const [isOpen, setIsOpen] = useState(false);

    return (
        <div className="w-full max-w-3xl bg-card rounded-lg border shadow-sm overflow-hidden">
            <Button
                variant="ghost"
                className="w-full flex items-center justify-between p-4 h-auto hover:bg-muted/50"
                onClick={() => setIsOpen(!isOpen)}
            >
                <div className="flex items-center gap-2 font-medium">
                    <SlidersHorizontal className="h-4 w-4" />
                    <span>Search Configuration</span>
                </div>
                {isOpen ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground" />
                ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                )}
            </Button>

            {isOpen && (
                <div className="p-6 pt-0 space-y-6 animate-in slide-in-from-top-2 duration-200">
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
            )}
        </div>
    );
}
