import os

def replace_in_file(filepath, replacements):
    with open(filepath, "r") as f:
        content = f.read()
    
    for old, new in replacements:
        if old not in content:
            print(f"WARNING: Could not find '{old[:30]}...' in {filepath}")
        content = content.replace(old, new)
        
    with open(filepath, "w") as f:
        f.write(content)

base = "../ak-distributors-public-web/src/"

# 1. Update page.tsx
page_replacements = [
    (
        'import Link from "next/link";', 
        'import Link from "next/link";\nimport { MotionRise } from "@/components/motion/MotionRise";\nimport { MotionReveal } from "@/components/motion/MotionReveal";'
    ),
    (
        '<div className="relative z-10 max-w-4xl mx-auto py-16">',
        '<MotionRise as="div" targets="children" stagger={100} className="relative z-10 max-w-4xl mx-auto py-16">'
    ),
    (
        '          </div>\n        </div>\n      </section>\n\n      {/* Marquee Section */}',
        '          </div>\n        </MotionRise>\n      </section>\n\n      {/* Marquee Section */}'
    ),
    (
        '<div className="grid md:grid-cols-3 gap-8">',
        '<MotionReveal as="div" targets="children" stagger={150} className="grid md:grid-cols-3 gap-8">'
    ),
    (
        '            </div>\n          </div>\n        </div>\n      </section>\n\n      {/* Latest Arrivals */}',
        '            </div>\n          </MotionReveal>\n        </div>\n      </section>\n\n      {/* Latest Arrivals */}'
    ),
    (
        '<div className="grid grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-8">',
        '<MotionReveal as="div" targets="children" stagger={100} className="grid grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-8">'
    ),
    (
        '              </Link>\n            ))}\n          </div>\n\n          <div className="mt-12 pt-8 border-t border-slate-100 flex justify-center w-full clear-both">',
        '              </Link>\n            ))}\n          </MotionReveal>\n\n          <div className="mt-12 pt-8 border-t border-slate-100 flex justify-center w-full clear-both">'
    )
]
replace_in_file(os.path.join(base, "app/page.tsx"), page_replacements)

# 2. Update products/page.tsx
products_replacements = [
    (
        'import Link from "next/link";',
        'import Link from "next/link";\nimport { MotionReveal } from "@/components/motion/MotionReveal";'
    ),
    (
        '<div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">',
        '<MotionReveal as="div" targets="children" stagger={50} className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">'
    ),
    (
        '              </Link>\n            ))}\n          </div>\n        ) : (',
        '              </Link>\n            ))}\n          </MotionReveal>\n        ) : ('
    )
]
replace_in_file(os.path.join(base, "app/products/page.tsx"), products_replacements)

print("Applied animations")
