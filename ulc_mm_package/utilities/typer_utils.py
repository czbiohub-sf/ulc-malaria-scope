import os
import typer

def choose_dir_get_files(dir):
    dirs = [x for x in sorted(os.listdir(dir)) if os.path.isdir(x)]

    typer.echo("The following folders were found: ")
    for i, dir in enumerate(dirs):
        typer.echo(f"{i}.\t{dir}/")

    num = -1
    while num not in list(range(len(dirs))):
        try:
            num = int(typer.prompt("Pick which directory you would like to view (enter the index number)"))
        except:
            pass
    
    chosen_dir = dirs[num]
    return [os.path.join(chosen_dir, x) for x in os.listdir(chosen_dir)]
