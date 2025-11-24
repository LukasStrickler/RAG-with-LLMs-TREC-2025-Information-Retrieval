"use client";

import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface SearchBarProps {
    value: string;
    onChange: (value: string) => void;
    onSearch: () => void;
    placeholder?: string;
}

export function SearchBar({
    value,
    onChange,
    onSearch,
    placeholder = "Search documents...",
}: SearchBarProps) {
    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter") {
            onSearch();
        }
    };

    const handleClear = () => {
        onChange("");
    };

    return (
        <div className="relative w-full max-w-3xl">
            <div className="relative flex items-center">
                <Search className="absolute left-4 h-5 w-5 text-muted-foreground" />
                <Input
                    type="text"
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    className="h-14 pl-12 pr-24 text-lg rounded-full border-2 focus-visible:ring-2 focus-visible:ring-blue-500 shadow-lg"
                    autoFocus
                />
                {value && (
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={handleClear}
                        className="absolute right-14 h-8 w-8 rounded-full"
                    >
                        <X className="h-4 w-4" />
                    </Button>
                )}
                <Button
                    onClick={onSearch}
                    className="absolute right-2 h-10 rounded-full bg-blue-600 hover:bg-blue-700 px-6"
                >
                    Search
                </Button>
            </div>
        </div>
    );
}
