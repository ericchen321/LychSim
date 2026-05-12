#include "Utils/argparse.h"
#include "Misc/Parse.h"
#include "Misc/CommandLine.h"

static FString JoinArray(const TArray<FString>& A)
{
	return FString::Printf(TEXT("[%s]"), *FString::Join(A, TEXT(", ")));
}

static FString JoinMap(const TMap<FString, FString>& M)
{
	TArray<FString> Pairs;
	Pairs.Reserve(M.Num());
	for (const TPair<FString, FString>& KV : M)
	{
		Pairs.Add(FString::Printf(TEXT("%s=%s"), *KV.Key, *KV.Value));
	}
	return FString::Printf(TEXT("{%s}"), *FString::Join(Pairs, TEXT(", ")));
}

static FString JoinSet(const TSet<FString>& S)
{
	TArray<FString> Items;
	Items.Reserve(S.Num());
	for (const FString& It : S)
	{
		Items.Add(It);
	}
	return FString::Printf(TEXT("{%s}"), *FString::Join(Items, TEXT(", ")));
}

namespace LychSim
{
	FParsedCmd ParseTailWithFParse(const FString& Tail)
    {
        FParsedCmd Out;

        const TCHAR* Cmd = *Tail;
        FString Tok;

        while (FParse::Token(Cmd, Tok, /*UseEscape*/ false))
        {
			if (!Tok.StartsWith(TEXT("-")) || Tok.Len() < 2)
			{
                Out.Positionals.Add(MoveTemp(Tok));
                continue;
            }

			// -.5 -0.5 -1
			const TCHAR NextChar = Tok[1];
            if (Tok.StartsWith(TEXT("-")) && (FChar::IsDigit(NextChar) || NextChar == TEXT('.')))
            {
                Out.Positionals.Add(MoveTemp(Tok));
                continue;
            }

            FString Sw = Tok.Mid(1);
            FString K, V;
            if (Sw.Split(TEXT("="), &K, &V))
			{
				K.TrimStartAndEndInline();
				V.TrimStartAndEndInline();
				Out.Kwargs.Add(MoveTemp(K), MoveTemp(V));
			}
            else
			{
				Sw.TrimStartAndEndInline();
				if (!Sw.IsEmpty())
				{
					Out.Flags.Add(MoveTemp(Sw));
				}
			}
        }

        return Out;
    }

    FString ParsedCmdToString(const FParsedCmd& Cmd)
    {
        return FString::Printf(
			TEXT("Args=%s | Kwargs=%s | Flags=%s"),
			*JoinArray(Cmd.Positionals),
			*JoinMap(Cmd.Kwargs),
			*JoinSet(Cmd.Flags)
		);
    }
}
