<p align="left">
<img src="https://github.com/Kreato-Linux/logo/blob/master/withtext.png"> 
</p>

# Kreato Linux official package repository
This is the Kreato Linux package repository. 
You should find the required packages for a nice base system here.

# Goals
* Have enough packages to get a GUI and browse the internet.
* Do it without having nonfree packages on the repository.

# Usage
Run `nyaa u`. This should automatically clone the repository. If it does not, [please file a bug report](https://github.com/kreatolinux/nyaa/issues).
If for some reason you need to clone it by hand, you can do so aswell.
```
git clone https://github.com/kreatolinux/nyaa-repo.git --depth=1 /etc/nyaa
```

# Development
Every package exists in a seperate directory.

* For runfiles, check out nyaa_run(8)
* Dependencies go onto the `deps` file. Each dependency should go onto a seperate line.
* Build dependencies go onto the `build_deps` file. Each dependency should go onto a seperate line.

After completing the package, run `sh migrate.sh nyaabinrepofolder packagefolder`. This script will convert your source package to a binary package and complete the process.
You can also make this binary package yourself if you want to do so.

# Credits
* Arch Linux packages
* Linux From Scratch packages
* KISS Linux packages.

Please note that this does not mean that the packages are taken from these projects, it just means that the packages have inspirations from these projects' packages aswell.

# License
This project is a part of Kreato Linux.

nyaa-repo is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

nyaa-repo is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with Kreato Linux.  If not, see <https://www.gnu.org/licenses/>.
