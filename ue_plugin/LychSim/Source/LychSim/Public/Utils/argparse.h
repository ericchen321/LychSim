# pragma once

#include "CoreMinimal.h"

#ifndef LYCHSIM_API
#define LYCHSIM_API
#endif

namespace LychSim
{
    struct LYCHSIM_API FParsedCmd
    {
        TArray<FString> Positionals;
		TMap<FString, FString> Kwargs;
		TSet<FString> Flags;

        FORCEINLINE FString Get(const TCHAR* Key) const
		{
			if (const FString* V = Kwargs.Find(Key)) return *V;
			return FString();
		}

		FORCEINLINE bool HasFlag(const TCHAR* Flag) const
		{
			return Flags.Contains(Flag);
		}
    };

    LYCHSIM_API FParsedCmd ParseTailWithFParse(const FString& Tail);

    FString ParsedCmdToString(const FParsedCmd& Cmd);
}
